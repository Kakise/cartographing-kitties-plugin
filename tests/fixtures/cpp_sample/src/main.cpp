#include "circle.h"
#include <iostream>

int main() {
    Circle c(1.5);
    geo::Triangle t(2.0, 3.0);
    std::cout << c.area() << '\n';
    std::cout << t.area() << '\n';
    return 0;
}

void free_func() {}
