import msgspec


class Point(msgspec.Struct, frozen=True):
    x: int
    y: int

    def __add__(self, other):
        if not isinstance(other, Point):
            return NotImplemented
        return Point(x=self.x + other.x, y=self.y + other.y)

    def __sub__(self, other):
        if not isinstance(other, Point):
            return NotImplemented
        return Point(x=self.x - other.x, y=self.y - other.y)

    def __abs__(self):
        return (self.x**2 + self.y**2) ** 0.5

    def __truediv__(self, other):
        if isinstance(other, int):
            return Point(x=self.x / other, y=self.y / other)
        return NotImplemented


class Size(msgspec.Struct, frozen=True):
    width: int
    height: int

    def total(self):
        return self.width * self.height

    def as_tuple(self):
        return (self.width, self.height)

    def as_numpy_shape(self):
        return (self.height, self.width)

    @classmethod
    def from_tuple(cls, tup):
        return cls(width=tup[0], height=tup[1])

    @classmethod
    def from_numpy_shape(cls, shape):
        return cls(height=shape[0], width=shape[1])


class Rect(msgspec.Struct, frozen=True):
    origin: Point
    spread: Size

    def as_pillow_box(self):
        return (
            self.origin.x,
            self.origin.y,
            self.origin.x + self.spread.width,
            self.origin.y + self.spread.height,
        )

    def __contains__(self, item):
        if not isinstance(item, Point):
            return NotImplemented
        min_x, min_y, max_x, max_y = self.as_pillow_box()
        return (
            item.x >= min_x and item.x <= max_x and item.y >= min_y and item.y <= max_y
        )


class ScreenInfo(msgspec.Struct, frozen=True):
    size: Size
    dpi: float
