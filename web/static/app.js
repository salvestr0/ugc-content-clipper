/* Viral Clipper — htmx config + Alpine.js helpers */

// Show error messages from htmx responses
document.addEventListener("htmx:responseError", function (evt) {
    const target = evt.detail.target;
    if (target) {
        target.innerHTML = '<p class="toast toast-error">Request failed. Check the server console.</p>';
    }
});

// After a job is created, redirect to the job detail page
document.addEventListener("htmx:afterRequest", function (evt) {
    if (evt.detail.requestConfig?.verb === "post" && evt.detail.requestConfig?.path === "/api/jobs") {
        const xhr = evt.detail.xhr;
        if (xhr.status >= 200 && xhr.status < 300) {
            try {
                const data = JSON.parse(xhr.responseText);
                if (data.id) {
                    window.location.href = "/jobs/" + data.id;
                }
            } catch (e) {
                // Not JSON, likely an HTML partial — let htmx handle it
            }
        }
    }
});
