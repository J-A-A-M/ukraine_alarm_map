# Arduino Async

This is a very simple library to run asynchronous functions on your sketch.


# Installation

* [Download](https://github.com/MatheusAlvesA/ArduinoAsync/archive/master.zip) the master branch on .zip format.
*  Unzip, then modify the Folder name to "Async"
* Paste the modified folder on your Library folder. Typically: `C:\Program Files (x86)\Arduino\libraries`

# How to use

First of all import the lib:
```c++
#include <async.h>
```
Instantiate the Async Class:
```c++
Async asyncEngine = Async();       // Allocate on Stack
      /* or */
Async *asyncEngine = new Async();  // Allocate on Heep
```
> **Note:** The examples above assume that you allocate the Async object on the Stack.
> If you allocate on Heep, use pointer dereferencing: "asyncEngine->"

Add the `run()` on the main loop function:
```c++
asyncEngine.run();
```
---

Execute every 10 milliseconds:
```c++
// id can be used later to stop the execution loop
short id = asyncEngine.setInterval(blinkLed, 10);
```
`blinkLed` code:
```c++
/*
  Blink the internal led every second.
	
  Using millis to avoid blocking code.
  Always avoid using delay function.
*/
void blinkLed() {
  static unsigned long start = millis();

  if((millis() - start) >= 500 && (millis() - start) < 1000) {
    digitalWrite(13, HIGH);
  }

  if((millis() - start) >= 1000) {
    digitalWrite(13, LOW);
    start = millis();
  }
}
```
If you just want to delay a execution of a function use `setTimeout`
```c++
// Delays the execution of a function by 10 seconds
asyncEngine.setTimeout(myFunction, 10000);
```
You can Stop the execution of a function previously added by calling `clearInterval`:
```c++
asyncEngine.clearInterval(id);
```

This full example can be found on [examples/blink_led.ino](https://github.com/MatheusAlvesA/ArduinoAsync/blob/master/examples/blink_led.ino "blink_led.ino").


# References

Constructor:
```c++
/*
  sizePool is the limit of functions that the engine can handle.
  Avoid using big numbers because of low memory available on Atmega.

  If you add more functions that sizePool the last functions added will be ignored.
*/
Async(unsigned short sizePool = 10)
```

setTimeout:
```c++
/*
  First param is the function that will be executed.
  Second param is the time to be waited before execute.

  The returned int value can be used to cancel the execution.
*/
short setTimeout(
  void (*fun)(void) = nullptr,
  unsigned long time = 0
)
```

setInterval:
```c++
/*
  First param is the function that will be executed.
  Second param is the time loop.

  The returned int value can be used to cancel the execution.
*/
short setInterval(
  void (*fun)(void) = nullptr,
  unsigned long time = 0
)
```

clearInterval:
```c++
/*
  Stop executing the function with the id passed
*/
bool clearInterval(short id = -1)
```

run:
```c++
/*
  Must be placed on the main loop.
*/
void run()
```
