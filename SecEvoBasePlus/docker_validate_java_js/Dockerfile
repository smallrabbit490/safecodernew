FROM node:20-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
RUN mkdir -p /work/lib \
    && curl -fsSL -o /work/lib/snakeyaml-1.33.jar https://repo1.maven.org/maven2/org/yaml/snakeyaml/1.33/snakeyaml-1.33.jar \
    && curl -fsSL -o /work/lib/json-20240303.jar https://repo1.maven.org/maven2/org/json/json/20240303/json-20240303.jar \
    && curl -fsSL -o /work/lib/gson-2.11.0.jar https://repo1.maven.org/maven2/com/google/code/gson/gson/2.11.0/gson-2.11.0.jar \
    && curl -fsSL -o /work/lib/commons-io-2.16.1.jar https://repo1.maven.org/maven2/commons-io/commons-io/2.16.1/commons-io-2.16.1.jar \
    && curl -fsSL -o /work/lib/commons-compress-1.26.2.jar https://repo1.maven.org/maven2/org/apache/commons/commons-compress/1.26.2/commons-compress-1.26.2.jar \
    && curl -fsSL -o /work/lib/jjwt-api-0.11.5.jar https://repo1.maven.org/maven2/io/jsonwebtoken/jjwt-api/0.11.5/jjwt-api-0.11.5.jar \
    && curl -fsSL -o /work/lib/jjwt-impl-0.11.5.jar https://repo1.maven.org/maven2/io/jsonwebtoken/jjwt-impl/0.11.5/jjwt-impl-0.11.5.jar \
    && curl -fsSL -o /work/lib/jjwt-jackson-0.11.5.jar https://repo1.maven.org/maven2/io/jsonwebtoken/jjwt-jackson/0.11.5/jjwt-jackson-0.11.5.jar \
    && curl -fsSL -o /work/lib/jackson-databind-2.17.2.jar https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-databind/2.17.2/jackson-databind-2.17.2.jar \
    && curl -fsSL -o /work/lib/jackson-core-2.17.2.jar https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-core/2.17.2/jackson-core-2.17.2.jar \
    && curl -fsSL -o /work/lib/jackson-annotations-2.17.2.jar https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-annotations/2.17.2/jackson-annotations-2.17.2.jar \
    && curl -fsSL -o /work/lib/javax.servlet-api-4.0.1.jar https://repo1.maven.org/maven2/javax/servlet/javax.servlet-api/4.0.1/javax.servlet-api-4.0.1.jar
COPY package.json /work/package.json
RUN npm install --omit=dev

COPY validate_java_js.py /work/validate_java_js.py

ENTRYPOINT ["python3", "/work/validate_java_js.py"]
