#include "ElbenchoHttpClient.h"
#include "Logger.h"

#ifdef S3_SUPPORT

std::shared_ptr<Aws::Http::HttpResponse> ElbenchoHttpClient::MakeRequest(
    const std::shared_ptr<Aws::Http::HttpRequest>& request,
    Aws::Utils::RateLimits::RateLimiterInterface* readLimiter,
    Aws::Utils::RateLimits::RateLimiterInterface* writeLimiter) const
{
    LOGGER(Log_DEBUG, "ElbenchoHttpClient::MakeRequest called - URI: " << request->GetURIString() 
           << " Method: " << static_cast<int>(request->GetMethod()) << std::endl);
    
    try {
        LOGGER(Log_DEBUG, "ElbenchoHttpClient::MakeRequest about to call base class" << std::endl);
        
        // Now let's try calling the base class method properly
        LOGGER(Log_DEBUG, "ElbenchoHttpClient::MakeRequest calling base class method" << std::endl);
        
        // Try calling the base class method using a different approach
        // Use the base class name without namespace to call the implementation
        auto response = CurlHttpClient::MakeRequest(request, readLimiter, writeLimiter);
        
        LOGGER(Log_DEBUG, "ElbenchoHttpClient::MakeRequest base class call succeeded" << std::endl);
        LOGGER(Log_DEBUG, "ElbenchoHttpClient::MakeRequest completed - Response code: " << 
               (response ? static_cast<int>(response->GetResponseCode()) : -1) << std::endl);
        
        return response;
    }
    catch (const std::exception& e) {
        LOGGER(Log_DEBUG, "ElbenchoHttpClient::MakeRequest exception: " << e.what() << std::endl);
        throw;
    }
    catch (...) {
        LOGGER(Log_DEBUG, "ElbenchoHttpClient::MakeRequest unknown exception" << std::endl);
        throw;
    }
}

#endif // S3_SUPPORT
