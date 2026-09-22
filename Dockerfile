FROM python:3.12-slim
WORKDIR /app
COPY app.py data.js ./
ENV PORT=8000
ENV DATA_DIR=/data
RUN mkdir -p /data
EXPOSE 8000
CMD ["python", "app.py"]
