FROM python:3.14-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72 AS build

WORKDIR /src

COPY pyproject.toml ./
COPY src ./src
COPY tests ./tests

RUN PYTHONPATH=/src/src python -m unittest discover -s tests -v \
    && python -m pip wheel --no-deps --wheel-dir /wheels .

FROM python:3.14-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72

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
