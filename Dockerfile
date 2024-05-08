FROM python:3.11-alpine

# This Dockerfile is set up for development

RUN apk update && \
    apk add --no-cache graphviz \
      ttf-freefont \
      bash \
      libffi-dev \
      gcc \
      musl-dev \
      git

COPY . ./app
WORKDIR ./app

RUN pip install -e --no-cache-dir .

CMD ["bash"]
