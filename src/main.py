from python_agent.agent import AgentApp
import logging
logging.basicConfig(
    format="[%(asctime)s %(levelname)s %(threadName)s %(name)s:%(funcName)s:%(lineno)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S%z",
)
logging.getLogger("council").setLevel("INFO")
import time

def main(test_case=None):
    agent_app = AgentApp(work_dir="./src/python_agent")
    agent_app.controller._state["code"] = None
    agent_app.controller._state["stderr"] = None

    if test_case:
        start_time = time.time()
        for message in test_case:
            print("Test Case User Message:", message)
            agent_app.interact(message, budget=600)
            print("Agent Response Message:", agent_app.context.chatHistory.last_agent_message.message)
            print("Agent Response Data:", agent_app.context.chatHistory.last_agent_message.data)
        end_time = time.time()
        print(f"Test case ran in {end_time-start_time:.1f} seconds.")
    else:
        while True:
            user_input = input("Enter something (or 'exit' to quit): ")

            if user_input.lower() == 'exit':
                print("Exiting the app.")
                break
            
            agent_app.interact(user_input, budget=600)
            print("Agent Response Message", agent_app.context.chatHistory.last_agent_message.message)
            print("Agent Response Data", agent_app.context.chatHistory.last_agent_message.data)

if __name__ == "__main__":

    # test case
    test_case = [
        "write code to compute the distance between two vectors",
        "please run it",
        "intentionally edit the code to cause an error",
        "run the code",
        "fix the error", 
        "execute the code please"
    ]

    test_case = [
        "write code to compute the distance between two vectors",
        "please run it",
        "can we do this but have it be between a vector and a matrix with ~10 rows?",
        "run the code",
    ]

    test_case = [
        "I want to create a virtual pet cat in pygame",
        "run it",
        "make the cat look nicer",
        "run it"
    ]

    main(test_case)
