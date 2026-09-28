#include <Servo.h>

Servo servo1, servo2, servo3, servo4;

int pos1, pos2, pos3, pos4;

const int STEP_FWD  = 15;
const int STEP_REV  = 8;
const int STEP_FAST = 1;

const int PIN_TX  = 11;
const int PIN_RX  = 12;
const int PIN_LED = 10;

int beamNormal;
unsigned long lastLedToggle = 0;

void blinkLed() {
  unsigned long now = millis();
  if (now - lastLedToggle >= 300) {
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
    lastLedToggle = now;
  }
}

void moveSingle(Servo &s, int &cur, int target, int ms) {
  while (cur != target) {
    cur += (target > cur) ? 1 : -1;
    s.write(cur);
    blinkLed();
    delay(ms);
  }
}

void moveDouble(Servo &sA, int &curA, int tA,
                Servo &sB, int &curB, int tB, int ms) {
  while (curA != tA || curB != tB) {
    if (curA != tA) { curA += (tA > curA) ? 1 : -1; sA.write(curA); }
    if (curB != tB) { curB += (tB > curB) ? 1 : -1; sB.write(curB); }
    blinkLed();
    delay(ms);
  }
}

void waitForBeamBreak() {
  unsigned long brokenSince = 0;
  while (true) {
    if (digitalRead(PIN_RX) != beamNormal) {
      if (brokenSince == 0) brokenSince = millis();
      if (millis() - brokenSince >= 10) break;
    } else {
      brokenSince = 0;
    }
  }
}

void waitForDetection() {
  while (true) {
    if (Serial.available() > 0) {
      char c = Serial.read();
      if (c == 'D') break;
    }
  }
}

void setup() {
  Serial.begin(9600);

  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);

  servo1.attach(3);
  servo2.attach(5);
  servo3.attach(6);
  servo4.attach(9);

  pos1 = 112; pos2 = 176; pos3 = 38; pos4 = 47;
  servo1.write(pos1);
  servo2.write(pos2);
  servo3.write(pos3);
  servo4.write(pos4);
  delay(1500);

  pinMode(PIN_TX, OUTPUT);
  digitalWrite(PIN_TX, HIGH);
  pinMode(PIN_RX, INPUT_PULLUP);
  delay(2000);
  beamNormal = digitalRead(PIN_RX);
  digitalWrite(PIN_LED, HIGH);
}

void loop() {
  waitForBeamBreak();
  Serial.println("B");

  waitForDetection();

  // ── Forward sequence ────────────────────────────────────────────
  moveSingle(servo1, pos1, 104,  STEP_FWD);
  moveDouble(servo2, pos2, 118, servo4, pos4,  95, STEP_FWD);
  moveSingle(servo1, pos1, 172,  STEP_FWD);
  moveDouble(servo2, pos2,  32, servo4, pos4, 180, STEP_FWD);
  moveSingle(servo3, pos3,  44,  STEP_FWD);
  moveSingle(servo4, pos4,   0,  STEP_FAST);

  // ── Reverse sequence ────────────────────────────────────────────
  moveSingle(servo4, pos4, 180,  STEP_REV);
  moveSingle(servo3, pos3,  38,  STEP_REV);
  moveDouble(servo2, pos2, 118, servo4, pos4,  95, STEP_REV);
  moveSingle(servo1, pos1, 104,  STEP_REV);
  moveDouble(servo2, pos2, 176, servo4, pos4,  47, STEP_REV);
  moveSingle(servo1, pos1, 112,  STEP_REV);

  Serial.println("R");

  while (digitalRead(PIN_RX) != beamNormal);
  delay(800);
  digitalWrite(PIN_LED, HIGH);
}
