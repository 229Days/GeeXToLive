import Vue from 'vue'
import Vuex from 'vuex'
import axios from 'axios'

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    tableData: []
  },
  mutations: {
    SET_TABLE_DATA(state, data) {
      state.tableData = data
    }
  },
  actions: {
    async fetchData({ commit }) {
      try {
        const response = await axios.get('http://localhost:5000/api/data')
        commit('SET_TABLE_DATA', response.data)
      } catch (error) {
        console.error(error)
      }
    }
  }
})
