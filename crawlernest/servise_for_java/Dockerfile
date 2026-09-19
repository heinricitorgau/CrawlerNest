# The Spring Boot read API.
#
# Two stages so the runtime image carries a JRE and one jar, not Maven and the
# whole dependency cache. The build stage warms that cache in its own layer, so
# editing a source file does not re-download it.
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /build

COPY pom.xml ./
RUN mvn -B -q dependency:go-offline

COPY src ./src
# Tests run in CI and need a database; the image build stays hermetic.
RUN mvn -B -q -DskipTests package

FROM eclipse-temurin:17-jre AS runtime
WORKDIR /app

# Never root: a read-only API has no business writing to its own image.
RUN useradd --system --uid 10001 --home /app crawlernest
COPY --from=build /build/target/*.jar /app/api.jar
USER crawlernest

EXPOSE 8080
# Every setting the app needs at runtime comes from the environment; see
# .env.example. The image carries no credentials.
ENV JAVA_OPTS=""
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/api.jar"]
