#include "widget.h"

Widget::Widget(int i) : id(i) {}

int Widget::get_id() const {
    return id;
}
