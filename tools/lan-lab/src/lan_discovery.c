#include "lan_discovery.h"

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#endif
#include <dns_sd.h>
#include <stdlib.h>
#include <string.h>

struct spple_discovery {
    DNSServiceRef service;
    spple_browse_callback browse;
    spple_resolve_callback resolve;
    spple_register_callback registered;
    spple_address_callback address;
    void *context;
};
static void DNSSD_API on_address(DNSServiceRef service,DNSServiceFlags flags,uint32_t index,DNSServiceErrorType error,
                                  const char *host,const struct sockaddr *address,uint32_t ttl,void *context) {
    (void)service;(void)host;(void)ttl;spple_discovery *op=context;
    if(error){op->address(op->context,error,index,NULL);return;}
    if(!(flags & kDNSServiceFlagsAdd) || !address || address->sa_family!=AF_INET)return;
    const struct sockaddr_in *ip=(const struct sockaddr_in *)address;
    op->address(op->context,0,index,(const uint8_t *)&ip->sin_addr);
}

static void DNSSD_API on_register(DNSServiceRef service, DNSServiceFlags flags, DNSServiceErrorType error,
                                   const char *name, const char *type, const char *domain, void *context) {
    (void)service; (void)flags; (void)name; (void)type; (void)domain;
    spple_discovery *op = context;
    op->registered(op->context, error);
}

static void DNSSD_API on_browse(DNSServiceRef service, DNSServiceFlags flags, uint32_t index,
                                 DNSServiceErrorType error, const char *name, const char *type,
                                 const char *domain, void *context) {
    (void)service;
    spple_discovery *op = context;
    op->browse(op->context, error, !!(flags & kDNSServiceFlagsAdd), index, name, type, domain);
}

static void DNSSD_API on_resolve(DNSServiceRef service, DNSServiceFlags flags, uint32_t index,
                                  DNSServiceErrorType error, const char *full_name, const char *host,
                                  uint16_t port, uint16_t txt_length, const unsigned char *txt, void *context) {
    (void)service; (void)flags; (void)full_name; (void)txt_length; (void)txt;
    spple_discovery *op = context;
    op->resolve(op->context, error, index, host, ntohs(port));
}

static int finish_start(spple_discovery **out, spple_discovery *op, DNSServiceErrorType result) {
    if (result != kDNSServiceErr_NoError) {
        if (op->service) DNSServiceRefDeallocate(op->service);
        free(op);
        return result;
    }
    *out = op;
    return 0;
}

int spple_discovery_advertise(spple_discovery **out, const char *name, uint16_t port) {
    return spple_discovery_advertise_observed(out, name, port, NULL, NULL);
}

int spple_discovery_advertise_observed(spple_discovery **out, const char *name, uint16_t port,
                                       spple_register_callback callback, void *context) {
    if (!out || !name || !*name || !port) return -1;
    *out = NULL;
    spple_discovery *op = calloc(1, sizeof(*op));
    if (!op) return -1;
    op->registered = callback;
    op->context = context;
    DNSServiceErrorType result = DNSServiceRegister(&op->service, 0, 0, name, SPPLE_LAN_SERVICE_TYPE,
                                                     NULL, NULL, htons(port), 0, NULL,
                                                     callback ? on_register : NULL, callback ? op : NULL);
    return finish_start(out, op, result);
}

int spple_discovery_browse(spple_discovery **out, spple_browse_callback callback, void *context) {
    if (!out || !callback) return -1;
    *out = NULL;
    spple_discovery *op = calloc(1, sizeof(*op));
    if (!op) return -1;
    op->browse = callback;
    op->context = context;
    DNSServiceErrorType result = DNSServiceBrowse(&op->service, 0, 0, SPPLE_LAN_SERVICE_TYPE,
                                                   NULL, on_browse, op);
    return finish_start(out, op, result);
}

int spple_discovery_resolve(spple_discovery **out, uint32_t index, const char *name,
                            const char *type, const char *domain, spple_resolve_callback callback, void *context) {
    if (!out || !name || !*name || !type ||
        (strcmp(type, SPPLE_LAN_SERVICE_TYPE) && strcmp(type, SPPLE_LAN_SERVICE_TYPE ".")) || !domain || !callback) return -1;
    *out = NULL;
    spple_discovery *op = calloc(1, sizeof(*op));
    if (!op) return -1;
    op->resolve = callback;
    op->context = context;
    DNSServiceErrorType result = DNSServiceResolve(&op->service, 0, index, name, type, domain, on_resolve, op);
    return finish_start(out, op, result);
}
int spple_discovery_address(spple_discovery **out,uint32_t index,const char *host,spple_address_callback callback,void *context) {
    if(!out || !host || !*host || !callback)return -1;*out=NULL;
    spple_discovery *op=calloc(1,sizeof(*op));if(!op)return -1;
    op->address=callback;op->context=context;
    DNSServiceErrorType result=DNSServiceGetAddrInfo(&op->service,0,index,kDNSServiceProtocol_IPv4,host,on_address,op);
    return finish_start(out,op,result);
}

int spple_discovery_fd(const spple_discovery *op) {
    return op && op->service ? DNSServiceRefSockFD(op->service) : -1;
}

int spple_discovery_process(spple_discovery *op) {
    return op && op->service ? DNSServiceProcessResult(op->service) : -1;
}

void spple_discovery_stop(spple_discovery *op) {
    if (!op) return;
    if (op->service) DNSServiceRefDeallocate(op->service);
    free(op);
}
