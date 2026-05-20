#ifndef CIRCLE_H
#define CIRCLE_H

#include "shape.h"

class Circle : public Shape {
public:
    double radius;
    Circle(double r);
    double area() const override;
};

enum class Color { Red, Green };

namespace geo {
class Triangle {
public:
    double base;
    double height;
    Triangle(double b, double h) : base(b), height(h) {}
    double area() const { return 0.5 * base * height; }
};
}  // namespace geo

#endif
