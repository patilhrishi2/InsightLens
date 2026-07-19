document.getElementById("student-button").addEventListener("click", function () {
    // Redirect to student dashboard or parsing page
    window.location.href = "/candidate/dashboard"; // Adjust this route as per your setup
});

document.getElementById("hr-button").addEventListener("click", function () {
    // Redirect to HR dashboard or parsing page
    window.location.href = "/hr-dashboard"; // If HR has a separate page, change this
});
