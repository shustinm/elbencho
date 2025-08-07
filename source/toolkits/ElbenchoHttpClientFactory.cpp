#include "ElbenchoHttpClientFactory.h"
#include "ElbenchoHttpClient.h"
#include "Logger.h"

#ifdef S3_SUPPORT
    #include <aws/core/http/standard/StandardHttpRequest.h>
    #include <aws/core/utils/memory/stl/AWSString.h>

    // Allocation tag for memory tracking
    static const char* FACTORY_ALLOCATION_TAG = "ElbenchoHttpClientFactory";

    std::shared_ptr<Aws::Http::HttpClient> ElbenchoHttpClientFactory::CreateHttpClient(
        const Aws::Client::ClientConfiguration& clientConfiguration) const
    {
        LOGGER(Log_DEBUG, "ElbenchoHttpClientFactory::CreateHttpClient called" << std::endl);
        
        // Return a shared pointer to our custom client, passing along the configuration
        auto client = Aws::MakeShared<ElbenchoHttpClient>(FACTORY_ALLOCATION_TAG, clientConfiguration);
        
        LOGGER(Log_DEBUG, "ElbenchoHttpClientFactory::CreateHttpClient created client" << std::endl);
        
        return client;
    }

    std::shared_ptr<Aws::Http::HttpRequest> ElbenchoHttpClientFactory::CreateHttpRequest(
        const Aws::String& uri, Aws::Http::HttpMethod method,
        const Aws::IOStreamFactory& streamFactory) const
    {
        // For requests, we can use the standard implementation
        return Aws::MakeShared<Aws::Http::Standard::StandardHttpRequest>(
            FACTORY_ALLOCATION_TAG, Aws::Http::URI(uri), method);
    }

    std::shared_ptr<Aws::Http::HttpRequest> ElbenchoHttpClientFactory::CreateHttpRequest(
        const Aws::Http::URI& uri, Aws::Http::HttpMethod method,
        const Aws::IOStreamFactory& streamFactory) const
    {
        return Aws::MakeShared<Aws::Http::Standard::StandardHttpRequest>(
            FACTORY_ALLOCATION_TAG, uri, method);
    }

    void ElbenchoHttpClientFactory::InitStaticState()
    {
        // Call the base class's static init for curl
        Aws::Http::CurlHttpClient::InitGlobalState();
    }

    void ElbenchoHttpClientFactory::CleanupStaticState()
    {
        // And cleanup here
        Aws::Http::CurlHttpClient::CleanupGlobalState();
    }

#endif // S3_SUPPORT
