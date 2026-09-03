FROM alpine:edge@sha256:020dfcbaaf4cc1078bf2d9c7ba31a8466e334061dcd2f248001d68f79e52c000
RUN apk add --no-cache python3 rspamd-client
RUN adduser -D -H -s /sbin/nologin learnspam
USER learnspam
WORKDIR /spamscan
COPY spamscan.py .
CMD ["python3", "spamscan.py"]
