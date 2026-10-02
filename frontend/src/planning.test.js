import test from 'node:test';
import assert from 'node:assert/strict';
import {calculatePlan, toCents} from './planning.js';
const plan = () => ({month:'2027-01',reserve:'100.00',extra_spending:'0.00',incomes:[{name:'Salary',amount:'5000.00'}],cards:[{name:'Visa',minimum:'75.00',balance:'2000.00'}],expenses:[{name:'Rent',amount:'1800.00'}],insurance:{premium:'800.00',percentage:'25.00',start_month:'2027-01'}});
test('monthly calculation includes minimums but not total debt',()=>{
 const result=calculatePlan(plan(),[{date:'2027-01-01',amount:'50.00'},{date:'2026-12-31',amount:'300.00'}]);
 assert.equal(result.available,277500);assert.equal(result.required,207500);assert.equal(result.debt,200000);
});
test('insurance begins at the month boundary and rounds half up',()=>{
 const p=plan();p.insurance.premium='100.05';p.insurance.percentage='10';p.month='2026-12';
 assert.equal(calculatePlan(p,[]).insurance,0);p.month='2027-01';assert.equal(calculatePlan(p,[]).insurance,1001);
});
test('independent theoretical edits change the result without mutating actual',()=>{
 const actual=plan(),theory=structuredClone(actual);theory.extra_spending='125';theory.insurance.percentage='50';
 assert.equal(calculatePlan(actual,[]).available-calculatePlan(theory,[]).available,32500);
 assert.equal(actual.insurance.percentage,'25.00');
});
test('bad money and invalid percentages never produce a misleading result',()=>{
 for(const value of ['', '-1','NaN','1.001','Infinity','1e4']) assert.throws(()=>toCents(value));
 const p=plan();p.insurance.percentage='101';assert.throws(()=>calculatePlan(p,[]));
 p.insurance.percentage='25';p.cards[0].minimum='2001';assert.throws(()=>calculatePlan(p,[]));
});
test('cent math and percentage math stay exact at large inputs',()=>{
 assert.equal(toCents('0.10')+toCents('0.20'),30);
 const p=plan();p.insurance.premium='9999999999.99';p.insurance.percentage='99.99';
 assert.equal(calculatePlan(p,[]).contribution,999899999999);
});
