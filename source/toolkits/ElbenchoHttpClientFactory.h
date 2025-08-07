#ifndef TOOLKITS_ELBENCHOHTTPCLIENTFACTORY_H_
#define TOOLKITS_ELBENCHOHTTPCLIENTFACTORY_H_

#ifdef S3_SUPPORT
    #include <aws/core/http/HttpClientFactory.h>
    #include <aws/core/client/ClientConfiguration.h>
    #include <aws/core/http/HttpRequest.h>
    #include <aws/core/http/URI.h>
    #include <aws/core/utils/memory/stl/AWSStreamFwd.h>

    class ElbenchoHttpClientFactory : public Aws::Http::HttpClientFactory
    {
    public:
        // The core method that creates our custom client
        std::shared_ptr<Aws::Http::HttpClient> CreateHttpClient(
            const Aws::Client::ClientConfiguration& clientConfiguration) const override;

        // These must also be implemented
        std::shared_ptr<Aws::Http::HttpRequest> CreateHttpRequest(
            const Aws::String& uri, Aws::Http::HttpMethod method,
            const Aws::IOStreamFactory& streamFactory) const override;

        std::shared_ptr<Aws::Http::HttpRequest> CreateHttpRequest(
            const Aws::Http::URI& uri, Aws::Http::HttpMethod method,
            const Aws::IOStreamFactory& streamFactory) const override;

        void InitStaticState() override;
        void CleanupStaticState() override;
    };

#endif // S3_SUPPORT

#endif // TOOLKITS_ELBENCHOHTTPCLIENTFACTORY_H_
