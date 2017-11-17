# JagerEye

JagerEye is a large distributed scale video analysis framework.

## Installation

* Install Python binding for OpenCV (>=2.4.0) that is compiled with FFmpeg.

```bash
# Install Python binding for OpenCV from distrubtion package or OpenCV compiled with FFmpeg.
# Please do not install from pip, it is not compiled with FFmpeg.
sudo apt-get install python-opencv
```

* Clone the project into your file system.

```bash
git clone https://github.com/SuJiaKuan/jagereye
```

* Go into the project directory.

```bash
cd ./jagereye
```

* Run the installation script.

```bash
sudo python setup.py install
```

## Development

### Test

* In the project root directory, run the test script to run tests automatically.

```bash
python setup.py test
```

### Lint

To lint the source code, please follow the following steps:

* Install [Pylint](https://www.pylint.org/)

* In the project root directory, run the lint script.

```bash
python setup.py lint
```

### Documentation

To generate the documentation, please follow the following steps:

* Install [Doxygen](http://www.stack.nl/~dimitri/doxygen/)

* In the project root directory, run the doc generating script, the generated documentation will be in `docs_output`.

```bash
python setup.py doc
```

## Contributing

### Coding Style Guildline

* Follow [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).

* To learn how to write docstrings, [Example Google Style Python Docstrings](http://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html) is a good example.

* See [Lint Section](#lint) to lint source code.

### Python 2 and 3 Compatible

* All code needs to be compatible with Python 2 and 3. [This](http://python-future.org/compatible_idioms.html) and [this](https://wiki.python.org/moin/PortingToPy3k/BilingualQuickRef) provide cheat sheets for writing Python 2 and 3 compatible code.

* The following lines must be present in all Python files:

```python
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
```

* Use [six](https://pypi.python.org/pypi/six) to write compatible code (for example `six.moves.range`).
