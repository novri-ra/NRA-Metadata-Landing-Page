const fs = require('fs');
const files = ['content.js', 'panel.js', 'background.js']; // Include background.js just in case

files.forEach(file => {
    if (fs.existsSync(file)) {
        let content = fs.readFileSync(file, 'utf8');
        content = content.replace(/\[Canva Automation\]/g, '[NRA DreamLab]');
        content = content.replace(/\[Canva Auto Prompter\]/g, '[NRA DreamLab]');
        content = content.replace(/Canva Auto Prompter/g, 'NRA DreamLab');
        fs.writeFileSync(file, content);
        console.log(`Updated ${file}`);
    }
});