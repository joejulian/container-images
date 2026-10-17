FROM python:3.15-alpine@sha256:e7044ccc46c44b6174e0051dbdcb84c79e19d0f2c398d28d5d45521ea42b01e2 AS build

WORKDIR /src

COPY pyproject.toml ./
COPY src ./src
COPY tests ./tests

RUN PYTHONPATH=/src/src python -m unittest discover -s tests -v \
    && python -m pip wheel --no-deps --wheel-dir /wheels .

FROM python:3.15-alpine@sha256:e7044ccc46c44b6174e0051dbdcb84c79e19d0f2c398d28d5d45521ea42b01e2

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup -g 1000 ota \
    && adduser -D -H -u 1000 -G ota ota

COPY --from=build /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels

USER 1000:1000
EXPOSE 8080

CMD ["android-update-server"]
