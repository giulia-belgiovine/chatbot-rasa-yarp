# chatbot-rasa-yarp
Yarp wrapper for a simple chatbot based on RASA conversational AI framework. Used on the robot iCub to integrate the architecture for person recognition task. 


#install RASA

pip3 install rasa

#command line interface

rasa train (to generate new models after changing the nlu)
rasa run actions

#on another shell:
rasa shell --endpoints endpoints.yml
