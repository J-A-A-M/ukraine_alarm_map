#include "async.h"

Async::Async(unsigned short sizePool) {
	nodePool = (ScheduleNode*) malloc(sizeof(ScheduleNode)*sizePool);
	for(unsigned short i = 0; i < sizePool; i++) {
        *(nodePool + i) = {
            .lastExecution = 0,
            .interval = 0,
            .flags = 0b00000010,
            .function = nullptr
		};
	}
	nNodes = 0;
	this->sizePool = sizePool;
}

short Async::setInterval(void (*fun)(void), unsigned long time) {
	if(fun == nullptr || nNodes >= sizePool)
		return -1;

	unsigned short i = 0;
	for(; i < sizePool; i++) {
        if((nodePool + i)->flags & 0b00000010) { // Is finished, bit 1
            *(nodePool + i) = {
                .lastExecution = millis(),
                .interval = time,
                .flags = 0b00000001,
                .function = fun
            };
            break;
        }
	}

	nNodes++;
	return i;
}

short Async::setTimeout(void (*fun)(void), unsigned long time) {
	if(fun == nullptr || nNodes >= sizePool)
		return -1;

    unsigned short i = 0;
	for(; i < sizePool; i++) {
        if((nodePool + i)->flags & 0b00000010) { // Is finished, bit 1
            *(nodePool + i) = {
                .lastExecution = millis(),
                .interval = time,
                .flags = 0b00000000,
                .function = fun
            };
            break;
        }
	}

	nNodes++;
	return i;
}

bool Async::clearInterval(short id) {
    if(id < 0 || (unsigned short) id >= sizePool)
        return false;

    (nodePool + id)->flags = 0b00000010; // Mark as finished, bit 1
    return true;
}

void Async::run() {
	for(unsigned short i = 0; i < sizePool; i++) {

        if(!((nodePool + i)->flags & 0b00000010)) { // Is not finished
           	unsigned long elapsedTime;
        	if(millis() < (nodePool + i)->lastExecution) { // Overflow detected
        		elapsedTime = (0xFFFFFFFFUL-(nodePool + i)->lastExecution) + millis();
            }
            else {
                elapsedTime = (millis() - (nodePool + i)->lastExecution);
            }

        	if(elapsedTime >= (nodePool + i)->interval) {
	            (nodePool + i)->function();
	            if(!((nodePool + i)->flags & 0b00000001)) { // Is not loop, bit 0
	                (nodePool + i)->flags = 0b00000010; // Mark as finished, bit 1
	                nNodes--;
	            } else {
	                (nodePool + i)->lastExecution = millis();
	            }
	        } // End elapsed time greater than interval of node
        } // End if node not finished

	} // End for
}

Async::~Async() {
	free(nodePool);
}
