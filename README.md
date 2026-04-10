# dccex-sbc-server
Emulate a [DCC-EX Command Station](https://dcc-ex.com/) to operate
servo and GPIO based model railroad accessories over TCP/IP using a
[Raspberry Pi](https://www.raspberrypi.org) Single Board Computer
(SBC).

This is a learning project of mine. I want to learn about Pythonʼs
[asyncio](https://docs.python.org/3/library/asyncio.html) features and
programming style and to understand I2C programming better. This is
also an API design exercise.

I plan to use this in “production” on my model railway, but I will
only test it is as far as I use it. Your milage may vary. Patches welcome. 

This project depends on:
* [rgpio](http://abyz.me.uk/lg/py_lgpio.html) 
  ([on pypi](https://pypi.org/project/lgpio/)) or 
  [lgpio](http://abyz.me.uk/lg/py_rgpio.html)
  ([on pypi](https://pypi.org/project/rgpio/))
* [i2cutils-lrgpio](https://github.com/dvorberg/i2cutils-lrgpio)
* [pca9685-lrgpio](https://github.com/dvorberg/pca9685-lrgpio) for servo 
  interaction
* [mcp23017-lrgpio](https://github.com/dvorberg/mcp23017-lrgpio) for 
  GPIO “Expander” interaction
