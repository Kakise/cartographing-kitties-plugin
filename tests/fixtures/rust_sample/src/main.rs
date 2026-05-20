use crate::geometry::Circle;
use std::collections::HashMap;

fn main() {
    let circle = Circle::new(1.5);
    let mut sizes: HashMap<String, f64> = HashMap::new();
    sizes.insert(String::from("unit"), circle.area());
    println!("area={}", circle.area());
}
