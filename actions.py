from typing import Any, Text, Dict, List, Union

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormAction, SlotSet
from rasa_sdk.types import DomainDict
from rasa_sdk.events import AllSlotsReset, Restarted

import csv
import pandas as pd
from datetime import datetime
import numpy as np
import os
import pathlib
import re
import time


class ActionWrongPerson(Action):

   def name(self):
      return "action_wrong_person"

   def run(self, dispatcher, tracker, domain):
      dispatcher.utter_message("Scusa, mi sono sbagliato!")
      return[SlotSet("first_name", None)]


class ActionRetrieveInformation(Action):

   def __init__(self):
        super().__init__()
        self.database_persons_df = pd.read_csv("AgentName/data/db_persons.csv")

   def name(self):
      return "action_retrieve_information"

   def run(self, dispatcher, tracker, domain):

       first_name = tracker.get_slot("first_name")
       row = self.database_persons_df.loc[self.database_persons_df['name'] == first_name]
       age = row.age.values[0]
       first_name = row.name.values[0]
       country = row.country.values[0]
       color = row.color.values[0]

       dispatcher.utter_message(text=f"slotValues-{first_name},{age},{country},{color}")

       return []


class ActionDefaultFallback(Action):

   def name(self):
      return "action_default_fallback"

   def run(self, dispatcher, tracker, domain):
      dispatcher.utter_message(response="utter_default")


class ActionReadMenu(Action):

    def __init__(self):
        super().__init__()

        self.week_day_dict = {1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 4: 'Thursday', 5: 'Friday', 6: 'Saturday',
                              7: 'Sunday'}
        self.week_day_ita = {'lunedì': 'Monday', 'martedì': 'Tuesday', 'mercoledì': 'Wednesday', 'giovedì': 'Thursday',
                             'venerdì': 'Friday', 'sabato': 'Saturday', 'domenica': 'Sunday'}

    def name(self) -> Text:
        return "action_read_menu"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        week_day = datetime.today().isoweekday()
        today_en = self.week_day_dict.get(week_day)

        with open('AgentLab/files_text/menu.csv', 'r') as file:
            reader = csv.reader(file)
            output = [row for row in reader if row[0] == today_en]
            print(output)

            if output:
                primi = [output[2] for output in output if output[1] == 'primo']
                secondi = [output[2] for output in output if output[1] == 'secondo']
                contorni = [output[2] for output in output if output[1] == 'contorno']

                reply1 = "Come primo oggi c'è {} ".format(primi)
                dispatcher.utter_message(text=reply1)
                time.sleep(0.5)
                reply2 = "come secondo invece abbiamo {} ".format(secondi)
                dispatcher.utter_message(text=reply2)
                time.sleep(0.5)
                reply3 = "e infine di contorno c'è {} ".format(contorni)
                dispatcher.utter_message(text=reply3)

        return []


class ActionReadLab(Action):

    def __init__(self):
        super().__init__()

        self.file_name_reddy = 'Reddy_November2021.csv'
        self.file_name_barry = 'Barry_Novembre2021.csv'
        self.file_name = self.file_name_barry

        self.reddy_list = ['redi', 'reddi', 'raddy', 'raddi', 'redy', 'reddy', 'red']
        self.barry_list = ['beri', 'berri', 'barry', 'barri', 'bery', 'berry', 'ber']

        self.week_day_dict = {1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 4: 'Thursday', 5: 'Friday', 6: 'Saturday',
                              7: 'Sunday'}
        self.week_day_ita = {'lunedì': 'Monday', 'martedì': 'Tuesday', 'mercoledì': 'Wednesday', 'giovedì': 'Thursday',
                             'venerdì': 'Friday', 'sabato': 'Saturday', 'domenica': 'Sunday'}

    def name(self) -> Text:
        return "action_read_lab"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        today = (datetime.today().strftime('%Y-%m-%d')).split('-')[-1]
        week_day = datetime.today().isoweekday()
        today_en = self.week_day_dict.get(week_day)

        if today[0] == '0':
            today = today[-1]

        req_day = tracker.get_slot("day")
        print("req_day is:", req_day)

        req_lab = tracker.get_slot("room")
        print("req_lab is:", req_lab)

        if req_lab is None:
            print("req lab is none")
            dispatcher.utter_message(text="Che laboratorio ti interessa? Reddy o Barry")

        elif req_day is None:
            print("req day is none")
            dispatcher.utter_message(text="Che giorno ti interessa?")

        else:
            if req_lab.lower() in self.reddy_list:
                self.file_name = self.file_name_reddy
            elif req_lab.lower() in self.barry_list:
                self.file_name = self.file_name_barry

            with open(os.path.join('AgentLab/files_text/', self.file_name), 'r') as file:
                df = pd.read_csv(file)

                tmp = np.array(df.where(df==today))
                coord = np.squeeze(np.argwhere(tmp==today))
                print(coord)

                if req_day == "oggi":
                    day_column = coord[1]
                elif req_day == "domani":
                    day_column = coord[1] + 1
                    print(coord)
                else:
                    req_day_en = self.week_day_ita.get(req_day)
                    week_index = coord[0] - 1
                    day_column = np.argwhere(np.array(df.loc[week_index] == req_day_en))
                    day_column = day_column[0][0]

                person = df.iloc[coord[0] + 1: coord[0] + 12, day_column]
                person = person.drop_duplicates()
                if str(person.values[0]) == 'nan':
                    print('person is', person.values[0])
                    dispatcher.utter_message(text="{} il laboratorio è libero".format(req_day))
                    return [AllSlotsReset()]
                else:
                    print('person is', person.values[0])
                    dispatcher.utter_message(text="{} il laboratorio è prenotato da {}".format(req_day, person.values[0]))
                    return [AllSlotsReset()]

        return []


class GeneralInfoForm(FormAction):

    def name(self):
        return "generalinfo_form"

    @staticmethod
    def required_slots(tracker):
        return ["first_name", "name_spelled_correctly", "age", "country", "color", "general"]

class SaveNewPerson(Action):

    def __init__(self):
        super().__init__()

        self.database_persons_file = "AgentName/data/db_persons.csv"

    def name(self) -> Text:
        return "save_new_person"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        file = open(self.database_persons_file, 'a', newline = '')
        writer = csv.writer(file)

        age = tracker.get_slot("age")
        first_name = tracker.get_slot("first_name")
        country = tracker.get_slot("country")
        # music = tracker.get_slot("music")
        color = tracker.get_slot("color")
        general = tracker.get_slot("general")

        row = [first_name, str(age), country, color, general]
        print("row is:", row)
        writer.writerow(row)

        file.close()

        return []


class ValidateGeneralForm(FormValidationAction):

    def __init__(self):
        super().__init__()

        self.names_list = pathlib.Path("AgentName/data/names.txt").read_text().split("\n")
        self.names_list = [x.lower() for x in self.names_list]

        self.country_list = pathlib.Path("AgentName/data/country.txt").read_text().split("\n")
        self.country_list = [x.lower() for x in self.country_list]

        self.database_persons_df = pd.read_csv("AgentName/data/db_persons.csv")

    def name(self) -> Text:
        return "validate_generalinfo_form"

    def validate_first_name(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate `first_name` value."""

        # If the name is super short, it might be wrong.
        first_name = tracker.get_slot("first_name")
        if len(first_name) <= 2:
            dispatcher.utter_message(response="utter_name_too_short")
            return {"first_name": None}

        list_word = first_name.split(" ")
        final_first_name = None
        for w in list_word:
            if w.lower() in self.names_list and len(w) > 2:
                final_first_name = w.lower()
                break

        if not final_first_name:
            return {"first_name": None}

        elif final_first_name in self.database_persons_df.name.values:
            row = self.database_persons_df.loc[self.database_persons_df['name'] == final_first_name]
            age = row.age.values[0]
            first_name = row.name.values[0]
            country = row.country.values[0]
            color = row.color.values[0]
            general = row.general.values[0]

            dispatcher.utter_message(text="Ah ma sei tu {}! Non ti avevo riconosciuto!".format(final_first_name))

            return {"requested_slot": None, "age": str(age), "first_name": final_first_name, "country": country, "color": color, "general": general}
        else:
            return {"first_name": final_first_name}

    def validate_age(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate age value."""
        dispatcher.utter_message(response="utter_answer_age")
        return {"age": tracker.get_slot("age")}

    def validate_general(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate age value."""
        # dispatcher.utter_message(response="utter_tellme_aboutyou")
        return {"general": tracker.get_slot("general")}

    def validate_country(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate age value."""
        country = tracker.get_slot("country")

        # list_word = country.split(" ")
        list_word = re.split(" |, |\*|\'", country)
        for w in list_word:
            if w.lower() in self.country_list and len(w) > 2:
                country = w.lower()
                dispatcher.utter_message(template="utter_answer_country", country=country)
                return {"country": country}

        return {"country": None}

    def validate_color(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate age value."""
        color = tracker.get_slot("color")

        if type(color) is list:
            color = color[0]

        print("color", color)
        dispatcher.utter_message(template="utter_answer_color", color=color)
        dispatcher.utter_message(response="utter_tellme_aboutyou")
        return {"color": color}

    def validate_music(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate age value."""
        dispatcher.utter_message(response="utter_answer_music")
        dispatcher.utter_message(response="utter_thanks")
        return {"music": tracker.get_slot("music")}

    def validate_name_spelled_correctly(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict,
    ) -> Dict[Text, Any]:

        print("validate name")
        intent = tracker.get_intent_of_latest_message()
        if intent == "affirm":
            dispatcher.utter_message(response="utter_answer_first_name")

            return {"first_name": tracker.get_slot("first_name"), "name_spelled_correctly": True}
        else:
            dispatcher.utter_message(response="utter_incorrect_name")

            return {"first_name": None, "name_spelled_correctly": None}


class ActionRestarted(Action):
    """ This is for restarting the chat"""

    def name(self):
        return "action_restart"

    def run(self, dispatcher, tracker, domain):
        return [Restarted()]

