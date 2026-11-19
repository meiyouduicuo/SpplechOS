#ifndef TEST_DNS_SD_H
#define TEST_DNS_SD_H
#include <stdint.h>
#define DNSSD_API
typedef struct fake_dns *DNSServiceRef;
typedef uint32_t DNSServiceFlags;
typedef int32_t DNSServiceErrorType;
typedef uint32_t DNSServiceProtocol;
struct sockaddr;
enum { kDNSServiceErr_NoError = 0, kDNSServiceFlagsAdd = 2, kDNSServiceProtocol_IPv4=1 };
typedef void (*DNSServiceBrowseReply)(DNSServiceRef, DNSServiceFlags, uint32_t, DNSServiceErrorType,
                                      const char *, const char *, const char *, void *);
typedef void (*DNSServiceResolveReply)(DNSServiceRef, DNSServiceFlags, uint32_t, DNSServiceErrorType,
                                       const char *, const char *, uint16_t, uint16_t, const unsigned char *, void *);
typedef void (*DNSServiceRegisterReply)(DNSServiceRef, DNSServiceFlags, DNSServiceErrorType,
                                        const char *, const char *, const char *, void *);
typedef void (*DNSServiceGetAddrInfoReply)(DNSServiceRef,DNSServiceFlags,uint32_t,DNSServiceErrorType,const char *,const struct sockaddr *,uint32_t,void *);
DNSServiceErrorType DNSServiceRegister(DNSServiceRef *, DNSServiceFlags, uint32_t, const char *, const char *,
                                      const char *, const char *, uint16_t, uint16_t, const void *, DNSServiceRegisterReply, void *);
DNSServiceErrorType DNSServiceBrowse(DNSServiceRef *, DNSServiceFlags, uint32_t, const char *, const char *,
                                    DNSServiceBrowseReply, void *);
DNSServiceErrorType DNSServiceResolve(DNSServiceRef *, DNSServiceFlags, uint32_t, const char *, const char *,
                                     const char *, DNSServiceResolveReply, void *);
DNSServiceErrorType DNSServiceGetAddrInfo(DNSServiceRef *,DNSServiceFlags,uint32_t,DNSServiceProtocol,const char *,DNSServiceGetAddrInfoReply,void *);
int DNSServiceRefSockFD(DNSServiceRef);
DNSServiceErrorType DNSServiceProcessResult(DNSServiceRef);
void DNSServiceRefDeallocate(DNSServiceRef);
#endif
