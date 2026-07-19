document.getElementById("register-form").addEventListener("submit", function(event) {
    event.preventDefault();

    const name = document.getElementById("name").value;
    const emailID = document.getElementById("emailID").value;
    const password = document.getElementById("password").value;
    const role = document.getElementById("role").value;

    if (!name || !emailID || !password || !role) {
        alert("All fields are required!");
        return;
    }

    fetch('/signup', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            name: name,
            email: emailID,
            password: password,
            role: role
        })
    })
    .then(response => {
        if (response.ok) {
            alert("Registration successful! Please login.");
            window.location.href = "/login";
        } else if (response.status === 409) {
            alert("Email already exists. Try another one.");
        } else {
            alert("Registration failed. Try again.");
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert("Error occurred. Try again.");
    });
});
