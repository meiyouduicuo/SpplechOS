#import <UIKit/UIKit.h>
#import <Foundation/Foundation.h>
#import <dispatch/dispatch.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <netinet/in.h>
#include <errno.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>
#include "lan_discovery.h"
#include "lan_handshake.h"
#include "lan_retry.h"

static const uint64_t kGame = UINT64_C(0x0100559011740000);

@interface LanProbe : UIResponder <UIApplicationDelegate>
@property(nonatomic, strong) UIWindow *window;
@property(nonatomic, strong) UILabel *status;
@property(nonatomic, strong) UIButton *hostButton;
@property(nonatomic, strong) UIButton *joinButton;
@property(nonatomic) spple_discovery *browser;
@property(nonatomic) spple_discovery *resolver;
@property(nonatomic) BOOL resolved;
@property(nonatomic) int discoveryError;
- (void)finish:(NSString *)text;
- (void)show:(NSString *)text;
- (void)setupWindow:(UIWindow *)window;
- (void)foundName:(const char *)name type:(const char *)type domain:(const char *)domain index:(uint32_t)index;
- (void)resolvedHost:(const char *)host port:(uint16_t)port error:(int)error;
@end

@interface ProbeScene : UIResponder <UIWindowSceneDelegate>
@property(nonatomic, strong) UIWindow *window;
@end

static void browse_event(void *context, int error, int added, uint32_t index,
                         const char *name, const char *type, const char *domain) {
    LanProbe *app = (__bridge LanProbe *)context;
    if (error) { app.discoveryError = error; return; }
    if (added && name && type && domain) [app foundName:name type:type domain:domain index:index];
}

static void register_event(void *context, int error) {
    LanProbe *app = (__bridge LanProbe *)context;
    if (error) app.discoveryError = error;
    else [app show:@"房间已创建，等待另一台设备连接…"];
}

static uint64_t monotonic_ms(void) {
    struct timespec time;
    if (clock_gettime(CLOCK_MONOTONIC, &time)) return 0;
    return (uint64_t)time.tv_sec * 1000 + (uint64_t)time.tv_nsec / 1000000;
}

static void resolve_event(void *context, int error, uint32_t index, const char *host, uint16_t port) {
    (void)index;
    [(__bridge LanProbe *)context resolvedHost:host port:port error:error];
}

static void prepare_socket(int fd) {
    int yes = 1;
    setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &yes, sizeof yes);
    struct timeval timeout = { .tv_sec = 10, .tv_usec = 0 };
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof timeout);
}

@implementation LanProbe
- (void)setupWindow:(UIWindow *)window {
    self.window = window;
    UIViewController *controller = [UIViewController new];
    controller.view.backgroundColor = [UIColor colorWithWhite:0.06 alpha:1];
    UILabel *title = [UILabel new];
    title.text = @"SpplechOS 局域网诊断"; title.textColor = UIColor.whiteColor;
    title.font = [UIFont boldSystemFontOfSize:25]; title.textAlignment = NSTextAlignmentCenter;
    self.status = [UILabel new]; self.status.textColor = UIColor.whiteColor;
    self.status.font = [UIFont systemFontOfSize:17]; self.status.numberOfLines = 0;
    self.status.textAlignment = NSTextAlignmentCenter;
    self.status.text = @"两台设备连接同一 Wi-Fi。一台点创建，另一台点查找。此程序只测试连接。";
    self.hostButton = [UIButton buttonWithType:UIButtonTypeSystem];
    [self.hostButton setTitle:@"创建测试房间" forState:UIControlStateNormal];
    self.joinButton = [UIButton buttonWithType:UIButtonTypeSystem];
    [self.joinButton setTitle:@"查找并连接" forState:UIControlStateNormal];
    self.hostButton.titleLabel.font = self.joinButton.titleLabel.font = [UIFont boldSystemFontOfSize:20];
    [self.hostButton addTarget:self action:@selector(startHost) forControlEvents:UIControlEventTouchUpInside];
    [self.joinButton addTarget:self action:@selector(startJoin) forControlEvents:UIControlEventTouchUpInside];
    UIStackView *stack = [[UIStackView alloc] initWithArrangedSubviews:@[title, self.status, self.hostButton, self.joinButton]];
    stack.axis = UILayoutConstraintAxisVertical; stack.spacing = 24; stack.translatesAutoresizingMaskIntoConstraints = NO;
    [controller.view addSubview:stack];
    NSLayoutConstraint *preferredWidth = [stack.widthAnchor constraintEqualToConstant:420];
    preferredWidth.priority = UILayoutPriorityDefaultLow;
    [NSLayoutConstraint activateConstraints:@[
        [stack.centerXAnchor constraintEqualToAnchor:controller.view.safeAreaLayoutGuide.centerXAnchor],
        [stack.centerYAnchor constraintEqualToAnchor:controller.view.safeAreaLayoutGuide.centerYAnchor],
        [stack.widthAnchor constraintLessThanOrEqualToAnchor:controller.view.safeAreaLayoutGuide.widthAnchor constant:-48],
        preferredWidth
    ]];
    self.window.rootViewController = controller; [self.window makeKeyAndVisible];
}
- (void)show:(NSString *)text { dispatch_async(dispatch_get_main_queue(), ^{ self.status.text = text; }); }
- (void)finish:(NSString *)text {
    dispatch_async(dispatch_get_main_queue(), ^{ self.status.text = text; self.hostButton.enabled = YES; self.joinButton.enabled = YES; });
}
- (void)disableButtons { self.hostButton.enabled = NO; self.joinButton.enabled = NO; }
- (void)startHost {
    [self disableButtons]; [self show:@"正在创建测试房间并等待设备…"];
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        int server = socket(AF_INET, SOCK_STREAM, 0);
        if (server < 0) { [self finish:@"无法创建网络连接，请重试。"]; return; }
        prepare_socket(server);
        struct sockaddr_in address = {0}; address.sin_len = sizeof address; address.sin_family = AF_INET;
        address.sin_addr.s_addr = htonl(INADDR_ANY); address.sin_port = 0;
        if (bind(server, (struct sockaddr *)&address, sizeof address) || listen(server, 1)) {
            close(server); [self finish:@"无法监听局域网连接，请检查本地网络权限后重试。"]; return;
        }
        socklen_t len = sizeof address;
        if (getsockname(server, (struct sockaddr *)&address, &len)) {
            close(server); [self finish:@"无法获取房间端口，请重试。"]; return;
        }
        spple_discovery *advertisement = NULL;
        char name[48]; snprintf(name, sizeof name, "Spple-LAN-%08x", arc4random());
        spple_lan_retry retry; spple_lan_retry_init(&retry, monotonic_ms(), 120000);
        self.discoveryError = 0;
        int peer = -1;
        while (spple_lan_retry_ready(&retry, monotonic_ms()) >= 0) {
            if (!advertisement) {
                if (!spple_lan_retry_ready(&retry, monotonic_ms())) { usleep(200000); continue; }
                self.discoveryError = 0;
                int err = spple_discovery_advertise_observed(&advertisement, name, ntohs(address.sin_port),
                                                               register_event, (__bridge void *)self);
                if (err) {
                    [self show:@"正在等待本地网络权限，允许后会自动重试…"];
                    if (spple_lan_retry_failure(&retry, monotonic_ms())) break;
                    continue;
                }
            }
            int dnsfd = spple_discovery_fd(advertisement);
            if (server >= FD_SETSIZE || dnsfd < 0 || dnsfd >= FD_SETSIZE) self.discoveryError = -1;
            if (!self.discoveryError) {
                fd_set set; FD_ZERO(&set); FD_SET(server, &set); FD_SET(dnsfd, &set);
                struct timeval wait = { .tv_sec = 0, .tv_usec = 500000 };
                int n = select((server > dnsfd ? server : dnsfd) + 1, &set, NULL, NULL, &wait);
                if (n < 0 && errno != EINTR) self.discoveryError = -1;
                if (n > 0 && FD_ISSET(dnsfd, &set)) {
                    int err = spple_discovery_process(advertisement);
                    if (err) self.discoveryError = err;
                }
                if (n > 0 && FD_ISSET(server, &set)) { peer = accept(server, NULL, NULL); if (peer >= 0) break; }
            }
            if (self.discoveryError) {
                spple_discovery_stop(advertisement); advertisement = NULL;
                [self show:@"正在等待本地网络权限，允许后会自动重试…"];
                if (spple_lan_retry_failure(&retry, monotonic_ms())) break;
            }
        }
        if (peer < 0) {
            spple_discovery_stop(advertisement); close(server);
            [self finish:@"等待超时。请确认本地网络权限及 Wi-Fi，然后点击按钮重试。"]; return;
        }
        prepare_socket(peer);
        uint8_t session[16]; arc4random_buf(session, sizeof session);
        int ok = spple_room_server_handshake(peer, kGame, session);
        close(peer); spple_discovery_stop(advertisement); close(server);
        [self finish:ok == 0 ? @"连接成功！两台设备已完成测试握手。\n这还不是游戏联机。" : @"连接已建立，但握手失败，可点击按钮重试。"];
    });
}
- (void)startJoin {
    [self disableButtons]; [self show:@"正在查找测试房间，请允许访问本地网络…"];
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        self.resolved = NO; self.discoveryError = 0;
        spple_lan_retry retry; spple_lan_retry_init(&retry, monotonic_ms(), 120000);
        while (!self.resolved && spple_lan_retry_ready(&retry, monotonic_ms()) >= 0) {
            if (!self.browser) {
                if (!spple_lan_retry_ready(&retry, monotonic_ms())) { usleep(200000); continue; }
                self.discoveryError = 0;
                int err = spple_discovery_browse(&_browser, browse_event, (__bridge void *)self);
                if (err) {
                    [self show:@"正在等待本地网络权限，允许后会自动重试…"];
                    if (spple_lan_retry_failure(&retry, monotonic_ms())) break;
                    continue;
                }
            }
            int a = spple_discovery_fd(self.browser), b = self.resolver ? spple_discovery_fd(self.resolver) : -1;
            if (a < 0 || a >= FD_SETSIZE || b >= FD_SETSIZE) self.discoveryError = -1;
            if (!self.discoveryError) {
                fd_set set; FD_ZERO(&set); FD_SET(a, &set); if (b >= 0) FD_SET(b, &set);
                struct timeval wait = { .tv_sec = 0, .tv_usec = 500000 };
                int highest = a > b ? a : b;
                int n = select(highest + 1, &set, NULL, NULL, &wait);
                if (n < 0 && errno != EINTR) self.discoveryError = -1;
                if (n > 0 && FD_ISSET(a, &set)) {
                    int err = spple_discovery_process(self.browser);
                    if (err) self.discoveryError = err;
                }
                if (n > 0 && b >= 0 && FD_ISSET(b, &set)) {
                    int err = spple_discovery_process(self.resolver);
                    if (err) self.discoveryError = err;
                }
            }
            if (self.discoveryError) {
                if (self.resolver) { spple_discovery_stop(self.resolver); self.resolver = NULL; }
                if (self.browser) { spple_discovery_stop(self.browser); self.browser = NULL; }
                [self show:@"等待网络权限或房间恢复，允许后会自动重试…"];
                if (spple_lan_retry_failure(&retry, monotonic_ms())) break;
            }
        }
        if (self.resolver) { spple_discovery_stop(self.resolver); self.resolver = NULL; }
        if (self.browser) { spple_discovery_stop(self.browser); self.browser = NULL; }
        [self finish:self.resolved ? @"连接成功！两台设备已完成测试握手。\n这还不是游戏联机。" : @"没有找到房间。请检查 Wi-Fi 和本地网络权限，再点击按钮重试。"];
    });
}
- (void)foundName:(const char *)name type:(const char *)type domain:(const char *)domain index:(uint32_t)index {
    if (self.resolver || self.resolved) return;
    int err = spple_discovery_resolve(&_resolver, index, name, type, domain, resolve_event, (__bridge void *)self);
    if (err) self.discoveryError = err;
}
- (void)resolvedHost:(const char *)host port:(uint16_t)port error:(int)error {
    if (self.resolved) return;
    if (error || !host || !port) { self.discoveryError = error ? error : -1; return; }
    [self show:@"已找到房间，正在连接…"];
    char service[8]; snprintf(service, sizeof service, "%u", port);
    struct addrinfo hints = {0}, *list = NULL; hints.ai_family = AF_INET; hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(host, service, &hints, &list) || !list) { self.discoveryError = -1; return; }
    int ok = -1;
    for (struct addrinfo *a = list; a; a = a->ai_next) {
        int fd = socket(a->ai_family, a->ai_socktype, a->ai_protocol);
        if (fd < 0) continue;
        prepare_socket(fd);
        if (!connect(fd, a->ai_addr, a->ai_addrlen)) {
            uint8_t session[16]; ok = spple_room_client_handshake(fd, kGame, session);
        }
        close(fd);
        if (!ok) break;
    }
    freeaddrinfo(list);
    if (ok == 0) {
        self.resolved = YES;
    } else self.discoveryError = -1;
}
@end

@implementation ProbeScene
- (void)scene:(UIScene *)scene willConnectToSession:(UISceneSession *)session options:(UISceneConnectionOptions *)options {
    (void)session; (void)options;
    if (![scene isKindOfClass:UIWindowScene.class]) return;
    self.window = [[UIWindow alloc] initWithWindowScene:(UIWindowScene *)scene];
    LanProbe *app = (LanProbe *)UIApplication.sharedApplication.delegate;
    [app setupWindow:self.window];
}
@end

int main(int argc, char **argv) {
    @autoreleasepool { return UIApplicationMain(argc, argv, nil, NSStringFromClass(LanProbe.class)); }
}
