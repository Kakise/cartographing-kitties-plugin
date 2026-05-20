#include "circle.h"
#include <vector>

Circle::Circle(double r) : radius(r) {}

double Circle::area() const {
    return 3.14159 * radius * radius;
}

namespace {
double anon_helper(double x) { return x * x; }
}

using StringList = std::vector<int>;
