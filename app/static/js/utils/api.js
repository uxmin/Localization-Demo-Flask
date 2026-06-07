export async function fetchData(url, formData) {
    try {
        const response = await fetch(url, {
            method: "POST",
            body: formData,
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        return data;
    }
    catch (error) {
        console.error("Fetch error: ", error);
        throw error;
    }
}
