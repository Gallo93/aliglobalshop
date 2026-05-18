FROM n8nio/n8n:latest

USER root
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5678
ENTRYPOINT ["/entrypoint.sh"]
CMD ["n8n", "start"]
