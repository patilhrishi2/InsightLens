document.getElementById("login-form").addEventListener("submit", async function (event) {
    event.preventDefault();

    const emailID = document.getElementById("emailID").value;
    const password = document.getElementById("password").value;
    const role = document.getElementById("role").value;

    if (!emailID || !password || !role) {
        alert("All fields are required!");
        return;
    }

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ emailID, password, role })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            alert('Login successful!');
            // Redirect to role-specific dashboard
            if (role === 'candidate') {
                window.location.href = '/candidate/dashboard';
            } else if (role === 'hr') {
                window.location.href = '/hr-dashboard';
            }
        } else {
            document.getElementById("error-message").style.display = "block";
        }

    } catch (error) {
        console.error('Error:', error);
        document.getElementById("error-message").style.display = "block";
    }
});
