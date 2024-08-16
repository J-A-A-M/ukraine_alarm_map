#ifndef Async_h
#define Async_h

#include "Arduino.h"

struct ScheduleNode {
	unsigned long lastExecution;
	unsigned long interval;       
	byte flags; //bit 0: is loop node; bit 1: is finished node.
	void (*function)(void);
};

class Async {
	private:
		ScheduleNode* nodePool;
		unsigned short nNodes;
		unsigned short sizePool;

	public:
		Async(unsigned short sizePool = 10);
		~Async();
		short setTimeout(void (*fun)(void) = nullptr, unsigned long time = 0);
		short setInterval(void (*fun)(void) = nullptr, unsigned long time = 0);
		bool clearInterval(short id = -1);
		void run();
};

#endif
