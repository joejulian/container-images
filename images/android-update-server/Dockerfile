FROM python:3.13-alpine AS build

WORKDIR /src

COPY pyproject.toml ./
COPY src ./src
COPY tests ./tests

RUN PYTHONPATH=/src/src python -m unittest discover -s tests -v \
    && python -m pip wheel --no-deps --wheel-dir /wheels .

FROM python:3.13-alpine

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
