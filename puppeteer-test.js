#! /usr/bin/env node
const puppeteer = require('puppeteer');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// wait 10 minutes
const wait = () =>
    new Promise((resolve) => setTimeout(resolve, 10 * 60 * 1000));

async function validateFile(dir, filename, expectedContent) {
    const filePath = path.join(dir, filename);
    const fileContent = await fs.promises.readFile(filePath, 'utf8');
    if (fileContent !== expectedContent) {
        throw new Error('file content did not match');
    }
}

function startShellCommand(command, args = [], envVars = {}) {
    const env = { ...process.env, ...envVars };

    const child = spawn(command, args, { shell: true, env });

    let stdoutData = '';
    let stderrData = '';

    child.stdout.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
        stdoutData += chunk;
    });

    child.stderr.setEncoding('utf8');
    child.stderr.on('data', (chunk) => {
        stderrData += chunk;
    });

    return {
        // Methods to retrieve the captured data
        getStdoutData: () => stdoutData,
        getStderrData: () => stderrData,

        // Pass data to the command's stdin
        writeToStdin: (data) => {
            if (!child.stdin.writable) {
                throw new Error(
                    'Cannot write to stdin: Stream is not writable'
                );
            }
            child.stdin.write(data);
        },

        kill: () => {
            child.kill();
        }
    };
}

const server = startShellCommand(
    './env/bin/flask', // Command
    ['run', '--debug', '--host', '0.0.0.0', '--port', '5555'],
    {
        MOUSEADMIN_DB: 'testdb.db',
        FLASK_APP: 'src/mouseadmin/app.py',
        WERKZEUG_DEBUG_PIN: 'off'
    }
);
new Promise((resolve) => setTimeout(resolve, 1000));

const test = async () => {

    /*************************
     * CREATE TEMPLATE
     *************************/

    const browser = await puppeteer.launch({ headless: false });
    const page = await browser.newPage();

    // Navigate to your page
    await page.goto('http://localhost:5555/templates/new');

    // Fill out the initial inputs
    await page.type('input[name="template_name"]', 'Example Template');
    await page.type(
        'input[name="entry_path_template"]',
        '/example/path/{{ myfield }}'
    );
    await page.type('input[name="neocities_path"]', '/neocities/example');

    // Add a new field
    await page.click('#new-field');

    // Fill out the new field's inputs
    const fieldSelector = '.fieldinput:not(.hidden)';
    await page.type(`${fieldSelector} input[name="field_name"]`, 'myfield');
    await page.select(`${fieldSelector} select[name="field_type"]`, 'text');

    // Add a select field
    await page.click('#new-field');
    const last = (elements) => elements[elements.length - 1];
    await last(await page.$$(`${fieldSelector} input[name="field_name"]`)).type(
        'myhtml'
    );
    await last(
        await page.$$(`${fieldSelector} select[name="field_type"]`)
    ).select('html');

    // Fill out the text areas
    await page.type(
        'textarea[name="index_template"]',
        '<h1>{{ myfield }}</h1>'
    );
    await page.type('textarea[name="entry_template"]', '<p>{{ myfield }}</p>');

    // Submit the form
    await page.click('input[type="submit"]');

    // Wait for the form submission to complete (you can add navigation or specific checks here if needed)
    await page.waitForNavigation();

    const exampleTemplateName = 'Example Template';
    const pageContent = await page.content();
    if (!pageContent.includes(exampleTemplateName)) {
        throw new Error(`Text "${exampleTemplateName}" not found on the page.`);
    }

    /*************************
     * UPDATE TEMPLATE
     *************************/

    // Click the template name "Example Template"
    await page.evaluate(() => {
        const link = Array.from(document.querySelectorAll('a')).find(
            (a) => a.textContent.trim() === 'Example Template'
        );
        link.click();
    });

    await page.waitForNavigation();

    // Click "edit template"
    await page.evaluate(() => {
        const link = Array.from(document.querySelectorAll('a')).find(
            (a) => a.textContent.trim() === 'Edit template'
        );
        link.click();
    });

    // Wait for navigation to the update form
    await page.waitForNavigation();

    // Clear the template name field
    await page.waitForSelector('input[name="template_name"]');
    await page.evaluate(() => {
        document.querySelector('input[name="template_name"]').value = '';
    });

    const newTemplateName = 'New Template Name';
    await page.type('input[name="template_name"]', newTemplateName);

    await page.click('input[type="submit"]');

    await page.waitForNavigation();

    if (!(await page.content()).includes(newTemplateName)) {
        throw new Error(`Text "${newTemplateName}" not found on the page.`);
    }

    /*************************
     * CREATE ENTRY
     *************************/

    await page.evaluate(() => {
        const link = Array.from(document.querySelectorAll('a')).find(
            (a) => a.textContent.trim() === 'New Template Name'
        );
        link.click();
    });

    await page.waitForNavigation();

    await page.evaluate(() => {
        const link = Array.from(document.querySelectorAll('a')).find(
            (a) => a.textContent.trim() === 'New entry'
        );
        link.click();
    });

    await page.waitForNavigation();

    await page.type('input[name="myfield"]', 'test');
    await page.type('textarea[name="myhtml"]', '<b>this is some html</b>');

    /* OBSERVE PREVIEW */
    await page.click('button[id="preview-button"]');

    await new Promise((resolve) => setTimeout(resolve, 1000));
    const previewPage = (await browser.pages())[2];
    if (!(await previewPage.content()).includes('test')) {
        throw new Error('Preview page does not contain variable');
    }

    if (!(await previewPage.$$('textarea')).name == 'myhtml') {
        throw new Error('Preview page does not contain html input');
    }
    await previewPage.close();

    /* SUBMIT */
    await page.click('input[type="submit"]');
    await page.waitForNavigation();
    if (!(await page.$$('li.entry')).innerText == '/example/path/test') {
        throw new Error('Page does not include newly created entry');
    }

    await validateFile('mock_data', '/example/path/test', '');

    /*************************
     * UPDATE ENTRY
     *************************/
    await page.click('li.entry > a');

    await page.waitForSelector('input[name="myfield"]');
    await page.evaluate(() => {
        document.querySelector('input[name="myfield"]').value = '';
    });
    await page.type('input[name="myfield"]', 'newvalue');
    await page.click('input[type="submit"]');
    await page.waitForNavigation();
    if (!(await page.$$('li.entry')).innerText == '/example/path/newvalue') {
        throw new Error('Page does not include newly updated entry');
    }

    console.log('done! :-)');
    server.kill();
    await browser.close();
};

(async () => {
    try {
        await test();
    } catch (e) {
        console.error("STDOUT");
        console.error(server.getStdoutData());
        console.error("--------------------------------------------------");
        console.error("STDERR");
        console.error(server.getStderrData());
        console.error("--------------------------------------------------");
        console.error(e);
        await wait();
    }
})();
