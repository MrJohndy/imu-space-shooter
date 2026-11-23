#include <Wire.h>
#include <math.h>

#define IMU_ADDRESS 0x6A

#define WHO_AM_I_REG 0x0F
#define CTRL1_XL     0x10
#define CTRL2_G      0x11
#define CTRL3_C      0x12
#define OUTX_L_G     0x22

const float GYRO_SCALE = 0.004375;
const float ALPHA = 0.98;

const int CALIBRATION_SAMPLES = 200;

int16_t gyroX, gyroY, gyroZ;
int16_t accelX, accelY, accelZ;

float gyroOffsetX = 0;
float gyroOffsetY = 0;
float gyroOffsetZ = 0;

float roll = 0;
float pitch = 0;
float yaw = 0;

unsigned long previousTime = 0;

// ==========================================
// I2C
// ==========================================

void writeRegister(byte reg, byte value) {
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

byte readRegister(byte reg) {
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(reg);
  Wire.endTransmission(false);

  Wire.requestFrom(IMU_ADDRESS, (byte)1);

  if (Wire.available()) {
    return Wire.read();
  }

  return 0;
}

int16_t readInt16() {
  byte lowByte = Wire.read();
  byte highByte = Wire.read();

  return (int16_t)((highByte << 8) | lowByte);
}

// ==========================================
// READ SENSOR
// ==========================================

bool readIMU() {
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(OUTX_L_G);

  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (Wire.requestFrom(IMU_ADDRESS, (byte)12) != 12) {
    return false;
  }

  gyroX = readInt16();
  gyroY = readInt16();
  gyroZ = readInt16();

  accelX = readInt16();
  accelY = readInt16();
  accelZ = readInt16();

  return true;
}

// ==========================================
// INITIALIZE SENSOR
// ==========================================

bool initializeIMU() {
  if (readRegister(WHO_AM_I_REG) != 0x70) {
    return false;
  }

  // Block data update + register auto-increment
  writeRegister(CTRL3_C, 0x44);

  // Accelerometer: 30 Hz, +/-2g
  writeRegister(CTRL1_XL, 0x04);

  // Gyroscope: 30 Hz, +/-125 dps
  writeRegister(CTRL2_G, 0x04);

  delay(100);

  return true;
}

// ==========================================
// GYROSCOPE CALIBRATION
// ==========================================

void calibrateGyroscope() {
  long sumX = 0;
  long sumY = 0;
  long sumZ = 0;

  Serial.println("STATUS,Keep Sensor Stable");
  Serial.println("CAL,0");

  for (int i = 0; i < CALIBRATION_SAMPLES; i++) {
    if (!readIMU()) {
      i--;
      delay(35);
      continue;
    }

    sumX += gyroX;
    sumY += gyroY;
    sumZ += gyroZ;

    if ((i + 1) % 2 == 0) {
      int progress =
        ((i + 1) * 100) / CALIBRATION_SAMPLES;

      Serial.print("CAL,");
      Serial.println(progress);
    }

    delay(35);
  }

  gyroOffsetX = (float)sumX / CALIBRATION_SAMPLES;
  gyroOffsetY = (float)sumY / CALIBRATION_SAMPLES;
  gyroOffsetZ = (float)sumZ / CALIBRATION_SAMPLES;

  if (readIMU()) {
    float ax = accelX;
    float ay = accelY;
    float az = accelZ;

    roll = atan2(ay, az) * RAD_TO_DEG;

    pitch = atan2(
      -ax,
      sqrt(ay * ay + az * az)
    ) * RAD_TO_DEG;
  }

  yaw = 0;

  Serial.println("READY");
}

// ==========================================
// UPDATE ORIENTATION
// ==========================================

void updateOrientation() {
  if (!readIMU()) {
    return;
  }

  unsigned long currentTime = micros();

  float dt = (currentTime - previousTime) / 1000000.0;

  previousTime = currentTime;

  if (dt <= 0 || dt > 0.2) {
    return;
  }

  // Gyroscope in degrees per second
  float gx = (gyroX - gyroOffsetX) * GYRO_SCALE;
  float gy = (gyroY - gyroOffsetY) * GYRO_SCALE;
  float gz = (gyroZ - gyroOffsetZ) * GYRO_SCALE;

  // Accelerometer angles
  float ax = accelX;
  float ay = accelY;
  float az = accelZ;

  float accelRoll =
    atan2(ay, az) * RAD_TO_DEG;

  float accelPitch =
    atan2(
      -ax,
      sqrt(ay * ay + az * az)
    ) * RAD_TO_DEG;

  // Complementary filter for roll and pitch
  roll =
    ALPHA * (roll + gx * dt) +
    (1.0 - ALPHA) * accelRoll;

  pitch =
    ALPHA * (pitch + gy * dt) +
    (1.0 - ALPHA) * accelPitch;

  // Z-axis gyro = yaw when the module is flat
  yaw += gz * dt;

  // Send roll, pitch, yaw to Python
  Serial.print(roll, 2);
  Serial.print(",");

  Serial.print(pitch, 2);
  Serial.print(",");

  Serial.println(yaw, 2);
}

// ==========================================
// SETUP
// ==========================================

void setup() {
  Serial.begin(115200);

  Wire.begin();
  Wire.setClock(100000);

  delay(100);

  if (!initializeIMU()) {
    Serial.println("ERROR,LSM6DSV_NOT_FOUND");

    while (true) {
      delay(100);
    }
  }

  calibrateGyroscope();

  previousTime = micros();
}

// ==========================================
// LOOP
// ==========================================

void loop() {
  updateOrientation();
}
