FROM python:3

WORKDIR /seg

COPY . .

RUN pip install --break-system-packages -r requirements.txt

ENTRYPOINT ["python", "./main.py"]
