ARG base_image="osgeo/gdal:ubuntu-small-3.0.2"
FROM $base_image as env_builder

# Set the locale, this is required for some of the Python packages
ENV LC_ALL C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install -y --fix-missing --no-install-recommends \
  python3 \
  python3-dev \
  python3-pip \
  python3-venv \
  libnetcdf-dev \
  libhdf4-alt-dev \
  libhdf5-serial-dev \
  libatlas-base-dev \
  gfortran \
  git \
  libudunits2-0 \
  libudunits2-dev \
  # copied from build-deps
  autoconf \
  automake \
  bzip2 \
  dpkg-dev \
  file \
  g++ \
  gcc \
  imagemagick \
  libbz2-dev \
  libc6-dev \
  libcurl4-openssl-dev \
  libdb-dev \
  libevent-dev \
  libffi-dev \
  libgdbm-dev \
  libglib2.0-dev \
  libgmp-dev \
  libjpeg-dev \
  libkrb5-dev \
  liblzma-dev \
  libmagickcore-dev \
  libmagickwand-dev \
  libmaxminddb-dev \
  libncurses5-dev \
  libncursesw5-dev \
  libpng-dev \
  libpq-dev \
  libreadline-dev \
  libsqlite3-dev \
  libssl-dev \
  libtool \
  libwebp-dev \
  libxml2-dev \
  libxslt-dev \
  libyaml-dev \
  make \
  patch \
  unzip \
  xz-utils \
  zlib1g-dev \
  && rm -rf /var/lib/apt/lists/*

# fix "missing libproj"
RUN ln -s /usr/local/lib/libproj.so.15 /usr/local/lib/libproj.so

# Install Tini
# tini is useful inside runners, it's easier to copy it from builder than download (which requires curl or wget)
RUN curl -s -L -O https://github.com/krallin/tini/releases/download/v0.18.0/tini \
  && echo "12d20136605531b09a2c2dac02ccee85e1b874eb322ef6baf7561cd93f93c855 *tini" | sha256sum -c - \
  && install -m 755 tini /bin/tini \
  && rm tini


RUN pip3 install --no-cache --no-cache-dir --upgrade \
         pip setuptools wheel cython numpy \
  && hash -r \
  && true

COPY requirements.txt /conf/requirements.txt
COPY ./dist/datacube-*tar.gz /conf/

RUN mkdir -p /wheels \
  && echo "GDAL==$(gdal-config --version)" > /tmp/constraints.txt \
  && find /conf -type f -name 'datacube-*tar.gz' | head -1 >> /tmp/constraints.txt \
  && cat /tmp/constraints.txt \
  && pip wheel \
  --no-cache \
  --no-cache-dir \
  --wheel-dir=/wheels \
  --find-links=/conf/ \
  --constraint=/tmp/constraints.txt \
  --requirement=/conf/requirements.txt \
  && rm /tmp/constraints.txt \
  && find /wheels/ -type f -name "datacube-*whl" -delete \
  && ls -lh /wheels/ \
  && echo "================================================================================"

COPY assets/env-build-tool /usr/local/bin/

# build environment with all dependencies of datacube but no datacube
RUN find /wheels/ -type f -name "*whl" > /tmp/reqs.txt \
# make env root:users with write permissions for group
  && (umask 002 \
  && mkdir -p /env \
  && chgrp users /env \
  && chmod g+s /env \
  && env-build-tool new /tmp/reqs.txt /wheels /env )


#################################################################################
# Runner stage
#################################################################################
FROM $base_image

# Set the locale, this is required for some of the Python packages
ENV LC_ALL C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive

# fix "missing libproj"
RUN ln -s /usr/local/lib/libproj.so.15 /usr/local/lib/libproj.so

RUN apt-get update \
  && apt-get install -y --fix-missing --no-install-recommends \
  python3 \
  python3-dev \
  python3-pip \
  python3-venv \
  libyaml-0-2 \
  # compliance checker
  libudunits2-0 \
  # netcdf4 libs
  libnetcdf-c++4 netcdf-bin \
  libhdf4-0-alt libhdf5-100 libhdf5-cpp-100 \
  # datacube tests need redis
  redis-server \
  # include db for running tests
  postgresql \
  postgresql-client-10 \
  postgresql-10 \
  # to become test user
  sudo \
  # git is needed for sdist|bdist_wheel
  git \
  && rm -rf /var/lib/apt/lists/*

# if using binary rasterio package, to support https
RUN mkdir -p /etc/pki/tls/certs \
&& ln -s /etc/ssl/certs/ca-certificates.crt /etc/pki/tls/certs/ca-bundle.crt;

# prep db
RUN  install --owner postgres --group postgres -D -d /var/run/postgresql /srv/postgresql \
  && sudo -u postgres "/usr/lib/postgresql/10/bin/initdb" -D "/srv/postgresql" --auth-host=md5 --encoding=UTF8

RUN groupadd --gid 1000 odc \
  && useradd --gid 1000 \
  --uid 1000 \
  --create-home \
  --shell /bin/bash -N odc \
  && adduser odc users \
  && adduser odc sudo \
  && echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers \
  && true

COPY --from=env_builder --chown=root:users /env /env
COPY --from=env_builder /bin/tini /bin/tini

COPY assets/with_bootstrap /usr/local/bin/

VOLUME /src/datacube-core
WORKDIR /src/datacube-core

ENTRYPOINT ["/bin/tini", "-s", "--", "/usr/local/bin/with_bootstrap"]
