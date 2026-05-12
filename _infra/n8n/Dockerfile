FROM n8nio/n8n:latest

USER root
RUN apk add --no-cache python3 py3-pip

USER node
EXPOSE 5678
CMD ["n8n", "start"]
