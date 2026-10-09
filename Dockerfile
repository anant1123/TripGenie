FROM python:3.11-slim

WORKDIR /app

# Install the libraries first (this layer is cached until requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# On a public website every visitor gets a private, temporary history
ENV STORAGE_MODE=session

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
