const resumeFile = document.getElementById("resumeFile");
const uploadBox = document.getElementById("uploadBox");
const fileName = document.getElementById("fileName");

const jobDescription = document.getElementById("jobDescription");
const characterCount = document.getElementById("characterCount");

const scanButton = document.getElementById("scanButton");
const loading = document.getElementById("loading");
const results = document.getElementById("results");


// -----------------------------
// Resume Upload
// -----------------------------

uploadBox.addEventListener("click", () => {
    resumeFile.click();
});


resumeFile.addEventListener("change", () => {

    if (resumeFile.files.length === 0) {
        fileName.textContent = "";
        return;
    }

    const file = resumeFile.files[0];

    // 5 MB limit
    if (file.size > 5 * 1024 * 1024) {

        alert("File is too large. Please select a file under 5MB.");

        resumeFile.value = "";
        fileName.textContent = "";

        return;
    }

    fileName.textContent = "✓ " + file.name;
});


// -----------------------------
// Character Counter
// -----------------------------

jobDescription.addEventListener("input", () => {

    characterCount.textContent =
        jobDescription.value.length;

});


// -----------------------------
// Scan Resume
// -----------------------------

scanButton.addEventListener("click", async () => {

    // Validate resume

    if (!resumeFile.files.length) {

        alert("Please upload your resume first.");

        return;
    }


    // Validate job description

    if (jobDescription.value.trim().length < 50) {

        alert(
            "Please enter a complete job description."
        );

        return;
    }


    // Show loading

    scanButton.disabled = true;

    loading.classList.remove("hidden");

    results.classList.add("hidden");


    const formData = new FormData();
    formData.append("resume", resumeFile.files[0]);
    formData.append("job_description", jobDescription.value.trim());

    try {
        const response = await fetch("/api/analyze", { method: "POST", body: formData });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "The analysis could not be completed.");
        showResults(data);
        results.classList.remove("hidden");
        results.scrollIntoView({ behavior: "smooth" });
    } catch (error) {
        alert(error.message);
    } finally {
        loading.classList.add("hidden");
        scanButton.disabled = false;
    }

});


// -----------------------------
// Display Results
// -----------------------------

function showResults(data) {

    const score = data.score;

    document.getElementById("score").textContent =
        score;


    document.getElementById("scoreMessage").textContent =
        data.message;


    renderSkills(
        "matchedSkills",
        data.matched_skills
    );


    renderSkills(
        "missingSkills",
        data.missing_skills
    );


    renderImprovements(
        data.improvements
    );

    document.querySelectorAll(".analysis-row").forEach(row => {
        const label = row.querySelector("span").textContent;
        const value = data.breakdown[label] || 0;
        row.querySelector(".progress-bar").style.width = `${value}%`;
        row.querySelector("strong").textContent = `${value}%`;
    });

}


// -----------------------------
// Render Skills
// -----------------------------

function renderSkills(elementId, skills) {

    const container =
        document.getElementById(elementId);

    container.innerHTML = "";

    skills.forEach(skill => {

        const element =
            document.createElement("span");

        element.className = "skill";

        element.textContent = skill;

        container.appendChild(element);

    });

}


// -----------------------------
// Render Improvements
// -----------------------------

function renderImprovements(items) {

    const container =
        document.getElementById("improvementList");

    container.innerHTML = "";

    items.forEach((item, index) => {

        const element =
            document.createElement("div");

        element.className =
            "improvement-item";

        element.innerHTML = `
            <div class="improvement-number">
                ${index + 1}
            </div>

            <div>
                ${item}
            </div>
        `;

        container.appendChild(element);

    });

}