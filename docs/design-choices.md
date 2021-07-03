<!--
SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>

SPDX-License-Identifier: CC-BY-SA-4.0
-->

# Tabula: Design choices


## NumPy and Pillow

[Pillow](https://pypi.org/project/Pillow/) is the default tool for image manipulation in Python. It works, the API isn't totally terrible, and you can do a lot with it. But the images we're working with here are 8-bit grayscale, and that's _essentially_ the same thing as a byte array, and that means [NumPy](https://numpy.org/) can be a pretty useful tool as well. It's just less intuitive for this.