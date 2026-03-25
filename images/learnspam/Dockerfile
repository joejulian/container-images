FROM alpine:edge
RUN apk add --no-cache python3 rspamd
RUN adduser -D -H -s /sbin/nologin learnspam
USER learnspam
WORKDIR /spamscan
COPY spamscan.py .
CMD ["python3", "spamscan.py"]
