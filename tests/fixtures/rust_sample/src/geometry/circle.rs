use super::Shape;

pub struct Circle {
    pub radius: f64,
}

impl Circle {
    pub fn new(radius: f64) -> Self {
        Circle { radius }
    }
}

impl Shape for Circle {
    fn area(&self) -> f64 {
        3.14159 * self.radius * self.radius
    }
}

pub fn unit_circle() -> Circle {
    Circle::new(1.0)
}
