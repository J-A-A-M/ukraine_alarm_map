#if TELNET_ENABLED
#include <TelnetSpy.h>

static TelnetSpy SerialAndTelnet;
#define LOG SerialAndTelnet
#else
#define LOG Serial
#endif
