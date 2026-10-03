const examApp = document.getElementById('exam-app');

if (examApp) {
  const examId = examApp.dataset.examId;
  const questionCard = document.getElementById('question-card');
  const questionCount = document.getElementById('question-count');
  const navGrid = document.getElementById('question-nav-grid');
  const timerElement = document.getElementById('timer');
  const previousButton = document.getElementById('previous-btn');
  const nextButton = document.getElementById('next-btn');
  const submitButton = document.getElementById('submit-btn');
  let questions = [];
  let answers = {};
  let currentIndex = 0;
  let secondsRemaining = 0;
  let submitted = false;

  const renderQuestion = () => {
    const question = questions[currentIndex];
    if (!question) return;
    const selected = answers[String(question.id)] || '';
    questionCount.textContent = `Question ${currentIndex + 1} of ${questions.length}`;
    questionCard.innerHTML = `<h2>${escapeHtml(question.question_text)}</h2><div class="option-list">${['A', 'B', 'C', 'D'].map((key) => `<label class="option ${selected === key ? 'selected' : ''}"><input type="radio" name="answer" value="${key}" ${selected === key ? 'checked' : ''}><span><strong>${key}.</strong> ${escapeHtml(question[`option_${key.toLowerCase()}`])}</span></label>`).join('')}</div>`;
    questionCard.querySelectorAll('input').forEach((input) => input.addEventListener('change', () => {
      answers[String(question.id)] = input.value;
      renderNav();
      renderQuestion();
    }));
    previousButton.disabled = currentIndex === 0;
    nextButton.textContent = currentIndex === questions.length - 1 ? 'Review answers' : 'Next →';
  };

  const renderNav = () => {
    navGrid.innerHTML = questions.map((question, index) => `<button type="button" class="nav-question ${index === currentIndex ? 'current' : ''} ${answers[String(question.id)] ? 'answered' : ''}" data-index="${index}">${index + 1}</button>`).join('');
    navGrid.querySelectorAll('button').forEach((button) => button.addEventListener('click', () => { currentIndex = Number(button.dataset.index); renderQuestion(); renderNav(); }));
  };

  const updateTimer = () => {
    const minutes = Math.floor(secondsRemaining / 60).toString().padStart(2, '0');
    const seconds = (secondsRemaining % 60).toString().padStart(2, '0');
    timerElement.textContent = `${minutes}:${seconds}`;
    if (secondsRemaining <= 60) timerElement.style.color = '#ffb7a4';
    if (secondsRemaining <= 0) submitExam(true);
    secondsRemaining -= 1;
  };

  const submitExam = async (automatic = false) => {
    if (submitted) return;
    if (!automatic && !window.confirm('Submit this examination now? You cannot change your answers afterward.')) return;
    submitted = true;
    submitButton.disabled = true;
    try {
      const response = await fetch(`/api/exams/${examId}/submit`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Unable to submit examination.');
      window.location.href = `/result/${payload.result_id}`;
    } catch (error) {
      submitted = false;
      submitButton.disabled = false;
      window.alert(error.message);
    }
  };

  const escapeHtml = (value) => { const element = document.createElement('div'); element.textContent = value; return element.innerHTML; };
  fetch(`/api/exams/${examId}/questions`).then((response) => response.json()).then((payload) => {
    if (!payload.questions) throw new Error(payload.error || 'Unable to load questions.');
    questions = payload.questions;
    answers = payload.answers || {};
    secondsRemaining = Number(payload.exam.duration) * 60;
    renderQuestion();
    renderNav();
    updateTimer();
    window.setInterval(updateTimer, 1000);
  }).catch((error) => { questionCard.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`; });

  previousButton.addEventListener('click', () => { if (currentIndex > 0) { currentIndex -= 1; renderQuestion(); renderNav(); } });
  nextButton.addEventListener('click', () => { if (currentIndex < questions.length - 1) { currentIndex += 1; renderQuestion(); renderNav(); } });
  submitButton.addEventListener('click', () => submitExam(false));
}
