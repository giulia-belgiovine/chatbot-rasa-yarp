import yarp
import sys

from rasa.core.agent import Agent, TrackerStore, DialogueStateTracker, Domain
from rasa.core.interpreter import RasaNLUInterpreter
from rasa.core.utils import EndpointConfig
from rasa.core.channels.channel import UserMessage
from rasa.shared.core.events import SlotSet
import asyncio


def yarpdebug(msg):
    print("[DEBUG]" + msg)


def yarpinfo(msg):
    print("[INFO] {}".format(msg))


class RasaModule(yarp.RFModule):

    def __init__(self):
        yarp.RFModule.__init__(self)

        # handle port for the RFModule
        self.handle_port = yarp.Port()
        self.attach(self.handle_port)

        self.process = False
        self.agent = None
        self.tracker = None
        self.loop = None
        self.name_set = False
        self.module_name = ""
        self.person_name = ""
        self.tracker_id = None

        # Input port
        self.cmd_port = yarp.BufferedPortBottle()
        self.user_msg_port = yarp.BufferedPortBottle()

        # Output port
        self.OPC_rpc = yarp.RpcClient()
        self.MOT_rpc = yarp.RpcClient()
        self.iSpeak = yarp.Port()
        self.event_port = yarp.Port()

        self.interpreter_name = ""
        self.model_name_path = ""
        self.interpreter_lab = ""
        self.model_lab_path = ""

        self.slot_values = None
        self.nlu_data = None
        self.current_agent = ""
        self.agentName = None
        self.agentLab = None
        self.interpreterName = None
        self.initAgentLab = False

    def configure(self, rf):

        self.module_name = rf.check("name",
                                    yarp.Value("rasaNLP"),
                                    "module name (string)").asString()

        self.interpreter_name = rf.find("interpreter_name").asString()
        self.model_name_path = rf.find("model_name_path").asString()
        self.interpreter_lab = rf.find("interpreter_lab").asString()
        self.model_lab_path = rf.find("model_lab_path").asString()

        # Create handle port to read message
        self.handle_port.open('/' + self.module_name)

        # Open ports
        self.OPC_rpc.open('/' + self.module_name + '/OPC_rpc:o')
        self.MOT_rpc.open('/' + self.module_name + '/MOT_rpc:o')
        self.cmd_port.open('/' + self.module_name + '/cmd:o')
        self.user_msg_port.open('/' + self.module_name + '/user_msg:i')
        self.iSpeak.open('/' + self.module_name + '/speak:o')
        self.event_port.open('/' + self.module_name + '/events:o')

        # Start RASA
        action_endpoint = EndpointConfig(url="http://localhost:5055/webhook")

        self.interpreterName = RasaNLUInterpreter(self.interpreter_name)
        self.agentName = Agent.load(model_path=self.model_name_path, interpreter=self.interpreterName,
                                    action_endpoint=action_endpoint)
        self.agentLab = Agent.load(model_path=self.model_lab_path, interpreter=self.interpreter_lab,
                                   action_endpoint=action_endpoint)

        self.agent = self.agentName
        self.current_agent = "AgentName"
        if self.agentName.is_ready() and self.agentLab.is_ready():
            yarpdebug("Initialization complete")
            return True
        else:
            yarpdebug("Initialization error")
            return False

    def interruptModule(self):
        yarpdebug("Stopping the module")
        self.handle_port.interrupt()
        self.cmd_port.interrupt()
        self.OPC_rpc.interrupt()
        self.MOT_rpc.interrupt()
        self.user_msg_port.interrupt()
        self.iSpeak.interrupt()
        self.event_port.close()
        return True

    def close(self):
        yarpdebug("Closing the module")
        self.handle_port.close()
        self.cmd_port.close()
        self.OPC_rpc.close()
        self.MOT_rpc.close()
        self.user_msg_port.close()
        self.iSpeak.close()
        self.event_port.close()
        return True

    def respond(self, command, reply):

        reply.clear()

        if command.get(0).asString() == "start":
            if command.get(1).asString() == "AgentLab":
                self.agent = self.agentLab
                self.current_agent = "AgentLab"
                self.initAgentLab = True
                self.process = True
                reply.addString("ok")
            else:
                self.tracker_id = command.get(1).asString()
                print("received command and tracker id:", self.tracker_id)
                self.process = True

                reply.addString("ok")

        elif command.get(0).asString() == "stop":
            self.process = False
            reply.addString("ok")

        elif command.get(0).asString() == "quit":
            reply.addString("quitting")
            return False

        elif command.get(0).asString() == "help":
            help_msg = "rasa Yarp module command are:"
            help_msg += "start/stop: To start and run the module"
            reply.addString(help_msg)

        return True

    def getPeriod(self):
        """
           Module refresh rate.
           Returns : The period of the module in seconds.
        """
        return 0.05

    def path_unknown(self):
        self.tracker = self.agent.tracker_store.get_or_create_tracker(sender_id="default")
        self.tracker.update(SlotSet("unknown_person", True))
        self.agent.tracker_store.save(self.tracker)
        yarpdebug("unknown_person : " + str(self.tracker.get_slot("unknown_person")))

    def path_known(self, recognized_name):
        self.tracker = self.agent.tracker_store.get_or_create_tracker(sender_id="default")
        self.tracker.update(SlotSet("first_name", recognized_name))
        self.tracker.update(SlotSet("unknown_person", False))
        self.agent.tracker_store.save(self.tracker)

    def analyse_intent(self, user_msg):
        nlu_data = self.loop.run_until_complete(self.agent.parse_message_using_nlu_interpreter(user_msg))
        if nlu_data["intent"]["name"] == "goodbye" and self.current_agent == "AgentLab":
            self.send_event("end_interaction")
            self.process = False
            self.agent = self.agentName
            self.current_agent = "AgentName"
            yarpdebug("SENT EVENT END")

    def analyze_answer(self, answer):
        for i in range(0, len(answer)):
            if 'text' in answer[i]:
                print(answer[i]['text'])
                if 'slotValues-' in answer[i]['text']:
                    tmp_str = answer[i]['text'].split("slotValues-")[-1].split(",")
                    self.slot_values = {key: val for key, val in
                                        zip(['first_name', 'age', 'country', 'color'], tmp_str)}
                    print("slot_values are:", self.slot_values)
                    name = self.slot_values.get("first_name")
                    self.set_tracker_label(name.strip())
                    # name = self.format_name(name)
                    print("label tracker set as {}".format(name))
                    self.send_event("slot_set")
                    self.name_set = False
                    self.process = False
                    self.tracker_id = None
                else:
                    self.write_iSpeak(answer[i]['text'])

    def updateModule(self):
        user_msg = None
        if self.user_msg_port.getInputCount():
            user_msg = self.user_msg_port.read(False)

        if self.process:

            self.loop = asyncio.get_event_loop()
            answer = ""

            if self.initAgentLab:
                answer = self.loop.run_until_complete(self.agent.handle_text("Ciao!", sender_id="default"))
                self.initAgentLab = False

            if not self.name_set and self.current_agent == "AgentName":
                self.person_name = self.get_name_in_memory(self.tracker_id)
                self.name_set = True

                if self.person_name != "unknown":
                    self.path_known(self.person_name)
                else:
                    self.path_unknown()
                answer = self.loop.run_until_complete(self.agent.handle_text("Ciao!", sender_id="default"))
                print(answer)

            elif user_msg:
                user_msg = user_msg.toString()
                user_msg = user_msg.replace("\"", "")
                answer = self.loop.run_until_complete(self.agent.handle_text(user_msg, sender_id="default"))
                self.analyse_intent(user_msg)
            else:
                pass

            if len(answer):
                self.analyze_answer(answer)

        return True

#############################################################################################

    def write_iSpeak(self, msg):
        """
        Send text to the speak module
        :param msg:
        :return: None
        """
        if self.iSpeak.getOutputCount():
            speak_bottle = yarp.Bottle()
            speak_bottle.clear()
            msg = "\\mrk=0\\" + msg + "\\mrk=1\\."
            speak_bottle.addString(msg)
            self.iSpeak.write(speak_bottle)

    def set_tracker_label(self, name):
        if self.OPC_rpc.getOutputCount():
            reply = yarp.Bottle()
            cmd = yarp.Bottle()
            cmd.addString("ask")
            list_condition = cmd.addList()
            cond1 = list_condition.addList()
            cond1.addString("id_tracker")
            cond1.addString("==")
            cond1.addString(self.tracker_id)

            # cmd = cmd.toString().replace('"', '')
            # cmd = yarp.Bottle(cmd)

            self.OPC_rpc.write(cmd, reply)

            list_id = reply.get(1).asList().get(1).asList()

            if list_id.size():
                print(reply.toString())
                cmd_fin = yarp.Bottle()
                cmd_fin.addString("set")
                list_prop = cmd_fin.addList()
                id_cmd = list_prop.addList()
                id_cmd.addString("id")
                id_cmd.addInt(list_id.get(0).asInt())
                label_cmd = list_prop.addList()
                label_cmd.addString("label_tracker")
                label_cmd.addString(name)
                ver_cmd = list_prop.addList()
                ver_cmd.addString("verified")
                ver_cmd.addInt(1)

                print("sent cmd to OPC", cmd_fin.toString())
                reply_2 = yarp.Bottle()
                self.OPC_rpc.write(cmd_fin, reply_2)

                return "ack" in reply_2.toString()
        return False

    def get_name_in_memory(self, tracker_id):

        if self.OPC_rpc.getOutputCount():
            reply = yarp.Bottle()
            cmd = yarp.Bottle()
            cmd.addString("ask")
            list_condition = cmd.addList()
            cond1 = list_condition.addList()
            cond1.addString("id_tracker")
            cond1.addString("==")
            cond1.addString(tracker_id)

            # cmd = cmd.toString().replace('"','')
            # cmd = yarp.Bottle(cmd)

            self.OPC_rpc.write(cmd, reply)
            print("sent cmd to OPC {}, and got answer {}".format(cmd.toString(), reply.toString()))
            list_id = reply.get(1).asList().get(1).asList()

            if list_id.size():
                cmd_str = "get ((id " + str(list_id.get(0).asInt()) + ') (propSet ("label_tracker")))'
                cmd_2 = yarp.Bottle(cmd_str)
                reply_2 = yarp.Bottle()

                self.OPC_rpc.write(cmd_2, reply_2)
                print("sent cmd to OPC {}, and got answer {}".format(cmd_2.toString(), reply_2.toString()))

                name = reply_2.get(1).asList().get(0).asList().get(1).asString()
                #TODO: if necessary format name string
                print("name is:", name)

                return name

    def format_name(self, name):
        name.strip()
        return name

    def send_event(self, event):
        """
        Send text to the speak module
        :param msg:
        :return: None
        """
        if self.event_port.getOutputCount():

            event_bottle = yarp.Bottle()
            event_bottle.clear()

            event_bottle.addString(event)
            self.event_port.write(event_bottle)


if __name__ == '__main__':

    # Initialise YARP
    if not yarp.Network.checkNetwork():
        print("Unable to find a yarp server exiting ...")
        sys.exit(1)

    yarp.Network.init()
    rasaModule = RasaModule()

    rf = yarp.ResourceFinder()
    rf.setVerbose(True)
    rf.setDefaultContext('rasabot')
    rf.setDefaultConfigFile("rasabot.ini")

    if rf.configure(sys.argv):
        rasaModule.runModule(rf)

    sys.exit()