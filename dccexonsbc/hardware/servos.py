from ..baseclasses import SetPulse, Servo

class SG90(Servo):
    minpulse = 0.5 / 1000 # ms ->   0°
    maxpulse = 2.5 / 1000 # ms -> 180°

    def pulse_for(self, angle:float) -> float:
        return (angle/180.0) * (self.maxpulse-self.minpulse) + self.minpulse

