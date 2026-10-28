# Build with the reviewed official nginx linux/amd64 digest as BASE_IMAGE.
ARG BASE_IMAGE=nginx@sha256:47928bf67eb62a1863cb08d9ecb52d3e704304ba614eaee17884204677702951
FROM ${BASE_IMAGE}
COPY nginx.conf /etc/nginx/nginx.conf
COPY dist/ /usr/share/nginx/html/
USER 101:101
EXPOSE 8080
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
