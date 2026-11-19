#include "lan_auth.h"
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <bcrypt.h>
#elif defined(__APPLE__)
#include <CommonCrypto/CommonHMAC.h>
#else
#error Unsupported crypto platform
#endif
int spple_lan_hmac(const void *key,size_t key_size,const void *data,size_t data_size,uint8_t out[32]) {
 if(!key || key_size<16 || key_size>64 || (!data && data_size) || !out || data_size>UINT32_MAX)return -1;
#ifdef _WIN32
 BCRYPT_ALG_HANDLE alg=NULL;BCRYPT_HASH_HANDLE hash=NULL;DWORD object_size=0,received=0;unsigned char *object=NULL;int rc=-1;
 if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,NULL,BCRYPT_ALG_HANDLE_HMAC_FLAG)<0)goto done;
 if(BCryptGetProperty(alg,BCRYPT_OBJECT_LENGTH,(PUCHAR)&object_size,sizeof object_size,&received,0)<0 || received!=sizeof object_size || !object_size)goto done;
 object=malloc(object_size);if(!object)goto done;
 if(BCryptCreateHash(alg,&hash,object,object_size,(PUCHAR)key,(ULONG)key_size,0)<0)goto done;
 if(data_size && BCryptHashData(hash,(PUCHAR)data,(ULONG)data_size,0)<0)goto done;
 if(BCryptFinishHash(hash,out,32,0)<0)goto done;rc=0;
done:
 if(hash)BCryptDestroyHash(hash);if(object){SecureZeroMemory(object,object_size);free(object);}if(alg)BCryptCloseAlgorithmProvider(alg,0);return rc;
#else
 CCHmac(kCCHmacAlgSHA256,key,key_size,data,data_size,out);return 0;
#endif
}
int spple_lan_tag_equal(const uint8_t a[32],const uint8_t b[32]) {
 if(!a || !b)return 0;unsigned char difference=0;for(int i=0;i<32;++i)difference|=a[i]^b[i];return difference==0;
}
