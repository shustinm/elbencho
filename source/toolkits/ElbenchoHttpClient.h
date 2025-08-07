#ifndef TOOLKITS_ELBENCHOHTTPCLIENT_H_
#define TOOLKITS_ELBENCHOHTTPCLIENT_H_

#ifdef S3_SUPPORT
    #include <aws/core/http/curl/CurlHttpClient.h>
    #include <aws/core/http/HttpRequest.h>
    #include <aws/core/http/HttpResponse.h>
    #include <aws/core/utils/ratelimiter/RateLimiterInterface.h>

    class ElbenchoHttpClient : public Aws::Http::CurlHttpClient
    {
    public:
        // Inherit the constructor from the base class
        using Aws::Http::CurlHttpClient::CurlHttpClient;

        // Override MakeRequest to intercept and modify the request before it is sent.
        std::shared_ptr<Aws::Http::HttpResponse> MakeRequest(
            const std::shared_ptr<Aws::Http::HttpRequest>& request,
            Aws::Utils::RateLimits::RateLimiterInterface* readLimiter = nullptr,
            Aws::Utils::RateLimits::RateLimiterInterface* writeLimiter = nullptr) const override;
    };

#endif // S3_SUPPORT

#endif // TOOLKITS_ELBENCHOHTTPCLIENT_H_
