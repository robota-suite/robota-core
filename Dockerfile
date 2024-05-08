FROM python:3.11-alpine

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

RUN pip install --no-cache-dir .

CMD ["bash"]
