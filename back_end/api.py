import os

from neo4j import GraphDatabase
from extractor import extract_teams
from summariser import summarise_two_team_matches_response
from chains import (
    configure_llm_only_chain,
    BaseLogger
)
from langchain_openai import ChatOpenAI
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from langchain.callbacks.base import BaseCallbackHandler
from threading import Thread
from queue import Queue, Empty
from collections.abc import Generator
from sse_starlette.sse import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware
import json
from dotenv import load_dotenv

class Question(BaseModel):
    text: str
    llmModel: str = "gpt-3.5"

class QueueCallback(BaseCallbackHandler):
    """Callback handler for streaming LLM responses to a queue."""

    def __init__(self, q):
        self.q = q

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.q.put(token)

    def on_llm_end(self, *args, **kwargs) -> None:
        return self.q.empty()

def stream(callback, queue) -> Generator:
    job_done = object()

    def task():
        x = callback()
        queue.put(job_done)

    t = Thread(target=task)
    t.start()

    content = ""

    # Get each new token from the queue and yield for our generator
    while True:
        try:
            next_token = queue.get(True, timeout=1)
            if next_token is job_done:
                break
            content += next_token
            yield next_token, content
        except Empty:
            continue

# Get values from .env, set up config and load chosen llm
load_dotenv(".env")

url = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
databaseName = os.getenv("NEO4J_DB_NAME")
llm_name = os.getenv("LLM")

def load_llm(llm_name: str, logger=BaseLogger(), config={}):
    if llm_name == "gpt-4":
        logger.info("LLM: Using GPT-4. WARNING: GPT-4 costs about 30x GPT-3.5")
        return ChatOpenAI(temperature=0, model_name="gpt-4", streaming=True)
    elif llm_name == "gpt-3.5":
        logger.info("LLM: Using GPT-3.5")
        return ChatOpenAI(temperature=0, model_name="gpt-3.5", streaming=True)
    elif llm_name == "gpt-3.5-turbo":
        logger.info("LLM: Using GPT-3.5-turbo")
        return ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo", streaming=True)
    elif llm_name == "mistral-large":
        logger.info("LLM: Using Mistral-Large model")
        print("Currently in development") # TODO: Complete all required changes to support Mistral Large deployed in Azure
        raise ValueError
    else:
        exit("Please specify an LLM. Options include gpt-4, gpt-3.5 and mistral-large") # TODO: Complete all required changes to support Mistral Large deployed in Azure

# Loads valid team names that have db data
def get_team_names():
    file_path = "team_names.txt"
    try:
        with open(file_path) as f:
            return f.read().splitlines() 
    except FileNotFoundError:
        print(f"The file '{file_path}' does not exist.")
    except Exception as e:
        print(f"An error occurred: {e}")

team_names = get_team_names()

# Create FastAPI app & permit all cross-origin requests
app = FastAPI()
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health-check endpoint
@app.get("/")
async def root():
    return {"message": "The pundit-bot backend is live!"}

# Standard entrypoint to pundit-bot. Call with query param text={question} to ask pundit-bot questions
@app.get("/query-stream")
def query_stream(question: Question = Depends()):

    try:
        llm = load_llm(llm_name=question.llmModel, logger=BaseLogger())
    except:
        print("unable to set up " + question.llmModel + ". Using gpt-3.5-turbo")
        llm = load_llm(llm_name="gpt-3.5-turbo", logger=BaseLogger())

    output_function = configure_llm_only_chain(llm)

    # extract from the question the 2 football teams mentioned
    csvTeams = extract_teams(question, llm)

    # Determine if the teams extracted are valid teams and included in our database
    csvTeamsSplitSuccessful = True
    try:
        [teamA, teamB] = csvTeams.split(", ")
        print("Extracted football teams: " + csvTeams + "\n\n")
        csvTeamsSplitSuccessful = False if teamA not in team_names or teamB not in team_names else True
    except ValueError:
        csvTeamsSplitSuccessful = False
    
    print(team_names)

    # if 2 valid teams were found, look them up in the neo4j graph
    if csvTeamsSplitSuccessful:
        print("Providing game data on teams\n\n")
        
        # Get all matches between 2 teams
        cypher_all_matches_between_two_teams = """MATCH (t:Match) 
        WHERE t.awayTeam = $teamA AND t.homeTeam = $teamB 
        OR t.awayTeam = $teamB AND t.homeTeam = $teamA
        RETURN properties(t)
        """

        with GraphDatabase.driver(url, auth=(username, password)) as driver:
            driver.verify_connectivity()

            records, summary, keys = driver.execute_query(
                cypher_all_matches_between_two_teams, 
                teamA=teamA, 
                teamB=teamB, 
                database_=databaseName
            )

            driver.close()

        # Summarise the response using the llm
        output_function = summarise_two_team_matches_response(llm, records)
    else:
        print("Unable to find 2 distinct teams; using llm response with no database data")

    # Create generate() method that returns the response in a stream of token-word pairs
    q = Queue()

    def callback():
        output_function(
            {"question": question.text, "chat_history": []},
            callbacks=[QueueCallback(q)],
        )

    def generate():
        yield json.dumps({"init": True, "model": llm_name})
        custom_stream = stream(callback, q)
        for token, _ in custom_stream:
            yield json.dumps({"token": token})

    return EventSourceResponse(generate(), media_type="text/event-stream")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8504)
