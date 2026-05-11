/**
 * @jest-environment jsdom
 */

// Mock dependencies
global.sendJson = jest.fn();
global.currentLetter = 'A';

const {
    toggleReady,
    stopGame,
    requestRestart,
    dissolveRoom,
    enableInputs,
    checkAllFilled,
    validateFirstLetter,
    disableAndSubmit
} = require('../static/js/game.js');

describe('Game Logic', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <button id="btn-draw"></button>
            <button id="btn-stop"></button>
            <div id="categories">
                <input data-category="panstwo" value="" />
                <input data-category="miasto" value="" />
            </div>
            <div id="restart-settings" style="display: none;"></div>
            <input id="restart-rounds" value="10" />
            <input id="restart-limit" value="60" />
            <div id="current-letter"></div>
        `;
        global.confirm = jest.fn(() => true);
        jest.clearAllMocks();
    });

    test('toggleReady switches state and sends json', () => {
        const btn = document.getElementById('btn-draw');
        toggleReady();
        expect(btn.classList.contains('ready')).toBe(true);
        expect(global.sendJson).toHaveBeenCalledWith({ type: 'ready' });

        toggleReady();
        expect(btn.classList.contains('ready')).toBe(false);
        expect(global.sendJson).toHaveBeenCalledWith({ type: 'not_ready' });
    });

    test('stopGame sends stop and disables inputs', () => {
        stopGame();
        expect(global.sendJson).toHaveBeenCalledWith({ type: 'stop' });
        expect(document.getElementById('btn-stop').disabled).toBe(true);
    });

    test('requestRestart sends restart_game and hides settings', () => {
        requestRestart();
        expect(global.sendJson).toHaveBeenCalledWith({
            type: 'restart_game',
            rounds: 10,
            limit: 60
        });
        expect(document.getElementById('restart-settings').style.display).toBe('none');
    });

    test('dissolveRoom sends json if confirmed', () => {
        dissolveRoom();
        expect(global.sendJson).toHaveBeenCalledWith({ type: 'dissolve_room' });
    });

    test('enableInputs resets inputs and clears timer', () => {
        globalThis.currentCountdown = setInterval(() => {}, 1000);
        enableInputs();
        expect(document.querySelectorAll('#categories input')[0].value).toBe('');
        expect(document.getElementById('current-letter').innerHTML).toBe('A');
    });

    test('checkAllFilled enables stop button only if all filled', () => {
        const inputs = document.querySelectorAll('#categories input');
        const stopBtn = document.getElementById('btn-stop');
        
        checkAllFilled();
        expect(stopBtn.disabled).toBe(true);

        inputs[0].value = 'Polska';
        inputs[1].value = 'Poznań';
        checkAllFilled();
        expect(stopBtn.disabled).toBe(false);
    });

    test('validateFirstLetter marks error if first letter mismatch', () => {
        const input = document.querySelector('#categories input');
        input.value = 'Warszawa'; // starts with W, currentLetter is A
        validateFirstLetter(input);
        expect(input.style.borderColor).toBe('var(--danger)');

        input.value = 'Amsterdam';
        validateFirstLetter(input);
        expect(input.style.borderColor).toBe('');
    });

    test('disableAndSubmit gathers answers and sends json', () => {
        const inputs = document.querySelectorAll('#categories input');
        inputs[0].value = 'Polska';
        inputs[1].value = 'Poznań';
        disableAndSubmit();
        expect(global.sendJson).toHaveBeenCalledWith({
            type: 'answers',
            answers: { 'panstwo': 'Polska', 'miasto': 'Poznań' }
        });
        expect(inputs[0].disabled).toBe(true);
    });
});
