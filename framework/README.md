# JagerEye Framework

The directory contains framework library for developing JagerEye applications.

## Installation

You can install framework on your host machine, or build Docker images that contain the framwork.

### On the Host

* Install Python 3.

* Install Python 3 binding for OpenCV (>=2.4.0) that is compiled with [Gstreamer](https://gstreamer.freedesktop.org/).

* Run the installation script.

```bash
sudo python3 setup.py install
```

### On Docker

* Run the Docker building script.

```bash
# Build docker images for both worker and brain
python3 setup.py docker

# Or, Build for worker only
python3 setup.py docker --target=worker

# Or, Build for brain only
python3 setup.py docker --target=brain
```

## Development

### Test

* Run the test script to run tests automatically.

```bash
pythons setup.py test
```

### Lint

To lint the source code, please follow the following steps:

* Install [Pylint](https://www.pylint.org/)

* Run the lint script.

```bash
python3 setup.py lint
```

### Documentation

To generate the documentation, please follow the following steps:

* Install [Doxygen](http://www.stack.nl/~dimitri/doxygen/)

* Run the document generating script, the generated documentation will be in `docs_output`.

```bash
python3 setup.py doc
```
