pub mod circle;

pub use self::circle::Circle;

pub trait Shape {
    fn area(&self) -> f64;
}

pub enum Kind {
    Round,
    Sharp,
}

pub type Coords = (f64, f64);
