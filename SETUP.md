TODO: This set up guide

- set up .env file
python -m venv .venv

- set up neo4j database

- set up back end
.\.venv\Scripts\activate
cd back_end
pip install -r requirements.txt
python back_end/api.py

- set up front end
python -m venv .venv
.\.venv\Scripts\activate
cd front_end; npm install; npm run dev

- Create docker container for project
Write Dockerfile in /back_end
`docker build -t pundit-bot-image .`
`docker run -d --name pundit-bot-container -p 80:80 pundit-bot-image